"""Doc repair engine: generate corrections, validate them, route by confidence.

Confidence-based routing:

================  =========================================================
Confidence        Action
================  =========================================================
high              Auto-fix: generate a correction and validate it.
medium            Draft fix: generate, wrap with REVIEW markers.
low               Flag only: no fix generated, request human review.
================  =========================================================

As with the staleness checker, a real provider drives generation/validation;
the mock provider falls back to deterministic targeted edits so the pipeline
yields concrete corrections offline.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from .config import Config
from .llm import LLMClient, get_llm_client
from .models import (
    ChangeType,
    CodeChange,
    Confidence,
    Correction,
    DocSection,
    RepairAction,
    StalenessFinding,
)
from .prompt_loader import render
from .staleness_checker import _default_literals, _params_from_signature, _sig_from_source

logger = logging.getLogger("docpilot.repair")

REVIEW_MARKER = "<!-- DOCPILOT: REVIEW NEEDED -->"


class RepairEngine:
    def __init__(self, config: Config, client: Optional[LLMClient] = None) -> None:
        self.config = config
        self.client = client or get_llm_client(config)

    def repair(
        self, finding: StalenessFinding, change: CodeChange, section: DocSection
    ) -> Correction:
        action = self._route(finding.confidence)

        if action is RepairAction.FLAG_ONLY:
            return Correction(
                doc_section_id=section.section_id,
                action=action,
                original_content=section.content,
                corrected_content=None,
                confidence=finding.confidence,
                diagnosis=finding.diagnosis,
                validation_passed=None,
                validation_notes="Low confidence: flagged for human review, no fix generated.",
            )

        corrected = self._generate(change, section, finding)
        if corrected is None:
            # Generation produced nothing usable -> degrade to a flag.
            return Correction(
                doc_section_id=section.section_id,
                action=RepairAction.FLAG_ONLY,
                original_content=section.content,
                corrected_content=None,
                confidence=finding.confidence,
                diagnosis=finding.diagnosis,
                validation_notes="Could not generate a targeted correction; flagged for review.",
            )

        if action is RepairAction.DRAFT_FIX:
            corrected = f"{REVIEW_MARKER}\n{corrected}"

        passed, notes = self._validate(change, section.content, corrected)
        return Correction(
            doc_section_id=section.section_id,
            action=action,
            original_content=section.content,
            corrected_content=corrected,
            confidence=finding.confidence,
            diagnosis=finding.diagnosis,
            validation_passed=passed,
            validation_notes=notes,
        )

    def _route(self, confidence: Confidence) -> RepairAction:
        if confidence is Confidence.HIGH:
            return RepairAction.AUTO_FIX
        if confidence is Confidence.MEDIUM:
            return RepairAction.DRAFT_FIX
        return RepairAction.FLAG_ONLY

    # -- generation ----------------------------------------------------------

    def _generate(
        self, change: CodeChange, section: DocSection, finding: StalenessFinding
    ) -> Optional[str]:
        if self.client.is_mock:
            return self._heuristic_generate(change, section, finding)
        try:
            system, user = render(
                "repair",
                diagnosis=finding.diagnosis,
                language="python",
                new_code=change.new_source or "(removed)",
                heading_path=section.heading_path,
                doc_content=section.content,
            )
            data = self.client.chat_json(system, user)
            corrected = data.get("corrected_content")
            return str(corrected) if corrected else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM repair failed, using heuristic: %s", exc)
            return self._heuristic_generate(change, section, finding)

    def _heuristic_generate(
        self, change: CodeChange, section: DocSection, finding: StalenessFinding
    ) -> Optional[str]:
        content = section.content

        if change.change_type is ChangeType.API_SIGNATURE:
            old_params = _params_from_signature(_sig_from_source(change.old_source))
            new_params = _params_from_signature(_sig_from_source(change.new_source))
            renames = _infer_renames(old_params, new_params)
            new_content = content
            for old, new in renames.items():
                new_content = _replace_word(new_content, old, new)
            return new_content if new_content != content else None

        if change.change_type is ChangeType.CONFIG_CHANGE:
            old_lits = _default_literals(change.old_source or "")
            new_lits = _default_literals(change.new_source or "")
            removed = sorted(old_lits - new_lits)
            added = sorted(new_lits - old_lits)
            if removed and added:
                new_content = content
                for old, new in zip(removed, added):
                    new_content = _replace_word(new_content, old, new)
                return new_content if new_content != content else None
            return None

        if change.change_type is ChangeType.FEATURE_ADDED:
            symbol = change.chunk_id.split("::")[-1].replace("env:", "")
            if symbol.isupper():
                return (
                    f"{content.rstrip()}\n\n"
                    f"- `{symbol}` -- _(newly added; document its purpose and default here)._"
                )
            return None

        if change.change_type is ChangeType.FEATURE_REMOVED:
            # Can't safely auto-delete prose; annotate for a reviewer instead.
            return (
                f"{REVIEW_MARKER}\n"
                f"> **Note:** `{change.chunk_id.split('::')[-1]}` was removed from the code. "
                f"The following documentation is now obsolete and should be deleted or updated.\n\n"
                f"{content}"
            )

        return None

    # -- validation ----------------------------------------------------------

    def _validate(
        self, change: CodeChange, original: str, corrected: str
    ) -> tuple[bool, str]:
        if self.client.is_mock:
            return self._heuristic_validate(change, original, corrected)
        try:
            system, user = render(
                "validate",
                language="python",
                new_code=change.new_source or "(removed)",
                original_content=original,
                corrected_content=corrected,
            )
            data = self.client.chat_json(system, user)
            passed = bool(data.get("passed", False))
            return passed, str(data.get("notes", ""))
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM validation failed, using heuristic: %s", exc)
            return self._heuristic_validate(change, original, corrected)

    def _heuristic_validate(
        self, change: CodeChange, original: str, corrected: str
    ) -> tuple[bool, str]:
        stripped = corrected.replace(REVIEW_MARKER, "").strip()
        if not stripped:
            return False, "Correction is empty."
        if stripped == original.strip():
            return False, "Correction is identical to the original."
        # New params / values should now appear in the corrected text.
        if change.change_type is ChangeType.API_SIGNATURE:
            new_params = _params_from_signature(_sig_from_source(change.new_source))
            old_params = _params_from_signature(_sig_from_source(change.old_source))
            stale = [p for p in (set(old_params) - set(new_params)) if re.search(rf"\b{re.escape(p)}\b", stripped)]
            if stale:
                return False, f"Correction still references removed params: {stale}."
        return True, "Heuristic validation passed: content changed and stale references removed."


def _infer_renames(old: list[str], new: list[str]) -> dict[str, str]:
    """Pair removed params with added params positionally as likely renames."""
    removed = [p for p in old if p not in new]
    added = [p for p in new if p not in old]
    return {o: n for o, n in zip(removed, added)}


def _replace_word(text: str, old: str, new: str) -> str:
    """Replace whole-word and inline-code occurrences of ``old`` with ``new``."""
    if not old:
        return text
    return re.sub(rf"(?<![\w]){re.escape(old)}(?![\w])", new, text)
