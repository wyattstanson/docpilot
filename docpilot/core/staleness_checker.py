"""LLM-based staleness verification -- the false-positive filter.

For each suspect doc section (one linked to a changed code chunk) the checker
decides whether the documentation is still accurate. With a real provider it
asks the LLM; offline (mock provider) it runs a deterministic heuristic that
covers the most common staleness patterns -- renamed params, changed defaults,
removed features -- so the pipeline produces real verdicts without a network.
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
    DocSection,
    StalenessFinding,
)
from .prompt_loader import render

logger = logging.getLogger("docpilot.staleness")

_CONFIDENCE = {"high": Confidence.HIGH, "medium": Confidence.MEDIUM, "low": Confidence.LOW}


def _params_from_signature(sig: Optional[str]) -> list[str]:
    if not sig:
        return []
    m = re.search(r"\(([^)]*)\)", sig)
    if not m:
        return []
    params = []
    for part in m.group(1).split(","):
        name = re.split(r"[:=]", part.strip())[0].strip().lstrip("*")
        if name and name not in {"self", "cls"}:
            params.append(name)
    return params


def _quoted_paths(source: str) -> list[str]:
    """Extract quoted URL-ish paths (e.g. ``"/legacy/stats"``) from source."""
    return re.findall(r"['\"](/[A-Za-z0-9_{}/:.-]*)['\"]", source)


def _default_literals(source: str) -> set[str]:
    """Pull RHS literals (numbers, strings, booleans) out of an assignment."""
    literals: set[str] = set()
    for m in re.finditer(r"=\s*([\"']?[\w./-]+[\"']?)", source):
        literals.add(m.group(1).strip("\"'"))
    return literals


class StalenessChecker:
    def __init__(self, config: Config, client: Optional[LLMClient] = None) -> None:
        self.config = config
        self.client = client or get_llm_client(config)

    def check(self, change: CodeChange, section: DocSection) -> StalenessFinding:
        if self.client.is_mock:
            return self._heuristic_check(change, section)
        try:
            return self._llm_check(change, section)
        except Exception as exc:  # noqa: BLE001 - never crash the pipeline
            logger.warning("LLM staleness check failed, using heuristic: %s", exc)
            return self._heuristic_check(change, section)

    # -- LLM path ------------------------------------------------------------

    def _llm_check(self, change: CodeChange, section: DocSection) -> StalenessFinding:
        system, user = render(
            "staleness_check",
            change_type=change.change_type.value,
            summary=change.summary,
            language="python",
            old_code=change.old_source or "(did not exist)",
            new_code=change.new_source or "(removed)",
            heading_path=section.heading_path,
            doc_content=section.content,
        )
        data = self.client.chat_json(system, user)
        confidence = _CONFIDENCE.get(str(data.get("confidence", "low")).lower(), Confidence.LOW)
        return StalenessFinding(
            doc_section_id=section.section_id,
            chunk_id=change.chunk_id,
            is_stale=bool(data.get("is_stale", False)),
            confidence=confidence,
            diagnosis=str(data.get("diagnosis", "")),
            change_type=change.change_type,
        )

    # -- heuristic path (offline) -------------------------------------------

    def _heuristic_check(self, change: CodeChange, section: DocSection) -> StalenessFinding:
        content = section.content.lower()
        refs = {r.lower() for r in section.code_references}

        def finding(is_stale: bool, conf: Confidence, diagnosis: str) -> StalenessFinding:
            return StalenessFinding(
                doc_section_id=section.section_id,
                chunk_id=change.chunk_id,
                is_stale=is_stale,
                confidence=conf,
                diagnosis=diagnosis,
                change_type=change.change_type,
            )

        if change.change_type is ChangeType.FEATURE_REMOVED:
            symbol = change.chunk_id.split("::")[-1].split(".")[-1].lower()
            if symbol in refs or symbol in content:
                return finding(
                    True, Confidence.HIGH,
                    f"Documentation still describes `{symbol}`, which was removed from the code.",
                )
            # A removed route/endpoint is often cited by its path, not its
            # function name -- match any quoted path from the old source.
            for path in _quoted_paths(change.old_source or ""):
                if path.lower() in content:
                    return finding(
                        True, Confidence.HIGH,
                        f"Documentation still describes the endpoint `{path}`, which was removed.",
                    )
            return finding(False, Confidence.LOW, "Removed symbol not referenced here.")

        if change.change_type is ChangeType.API_SIGNATURE:
            old_params = set(_params_from_signature(_sig_from_source(change.old_source)))
            new_params = set(_params_from_signature(_sig_from_source(change.new_source)))
            removed = old_params - new_params
            added = new_params - old_params
            stale_params = [p for p in removed if p.lower() in content or p.lower() in refs]
            if stale_params:
                return finding(
                    True, Confidence.HIGH,
                    f"Documentation references parameter(s) {stale_params} that were "
                    f"renamed or removed (new params: {sorted(added) or 'none'}).",
                )
            if added and any(_mentions_params(content)):
                return finding(
                    True, Confidence.MEDIUM,
                    f"New parameter(s) {sorted(added)} are not documented.",
                )
            return finding(False, Confidence.LOW, "Signature changed but docs do not cite the affected params.")

        if change.change_type is ChangeType.CONFIG_CHANGE:
            old_lits = _default_literals(change.old_source or "")
            new_lits = _default_literals(change.new_source or "")
            removed_lits = old_lits - new_lits
            stale_lits = [l for l in removed_lits if l and l.lower() in content]
            if stale_lits:
                return finding(
                    True, Confidence.HIGH,
                    f"Documentation states old default value(s) {stale_lits}; "
                    f"the code now uses {sorted(new_lits - old_lits) or 'a new value'}.",
                )
            return finding(False, Confidence.LOW, "Config changed but no stale default found in the docs.")

        if change.change_type is ChangeType.FEATURE_ADDED:
            symbol = change.chunk_id.split("::")[-1].replace("env:", "")
            is_config_like = symbol.isupper() and len(symbol) > 1
            doc_is_config = any(
                kw in content for kw in ("environment variable", "config", "setting", "env var")
            )
            if is_config_like and doc_is_config and symbol.lower() not in content:
                return finding(
                    True, Confidence.MEDIUM,
                    f"New configuration variable `{symbol}` is not documented in this "
                    f"section, which currently enumerates the available settings.",
                )
            return finding(False, Confidence.LOW, "New feature; linked section appears unrelated.")

        if change.change_type is ChangeType.BEHAVIOR_CHANGE:
            return finding(
                False, Confidence.LOW,
                "Behavioral change detected; manual review recommended but no concrete inaccuracy found.",
            )

        return finding(False, Confidence.LOW, "No staleness detected.")


def _sig_from_source(source: Optional[str]) -> Optional[str]:
    if not source:
        return None
    m = re.search(r"(?:async\s+)?def\s+\w+\s*\([^)]*\)", source)
    if m:
        return m.group(0)
    m = re.search(r"function\s+\w+\s*\([^)]*\)", source)
    return m.group(0) if m else None


def _mentions_params(content: str) -> list[bool]:
    return [kw in content for kw in ("parameter", "argument", "param", "arg ")]
