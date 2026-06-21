"""End-to-end orchestration of the DocPilot engine.

The :class:`Pipeline` wires the parser, embedding store, linker, diff analyzer,
staleness checker and repair engine together and exposes the two operations the
rest of the system needs:

* :meth:`build_mapping` -- (re)build and persist ``.docpilot/mapping.json``.
* :meth:`run` -- given a base/head ref (or the working tree), detect stale doc
  sections and produce corrections, returning a :class:`PipelineReport`.

A third helper, :meth:`check_pasted`, powers the dashboard's live console: it
runs the full staleness+repair logic on an ad-hoc code diff and doc section
with no repository or git required.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .config import Config
from .diff_analyzer import DiffAnalyzer
from .embeddings import EmbeddingStore
from .linker import Linker
from .models import (
    ChangeType,
    CodeChange,
    Confidence,
    Correction,
    DocSection,
    Mapping,
    RepairAction,
    StalenessFinding,
    utc_now_iso,
)
from .parser import CodeParser, DocParser, Language
from .repair_engine import RepairEngine
from .staleness_checker import StalenessChecker

logger = logging.getLogger("docpilot.pipeline")


@dataclass
class PipelineReport:
    """The result of a detection run."""

    generated_at: str = field(default_factory=utc_now_iso)
    sections_checked: int = 0
    findings: list[StalenessFinding] = field(default_factory=list)
    corrections: list[Correction] = field(default_factory=list)

    @property
    def stale_findings(self) -> list[StalenessFinding]:
        return [f for f in self.findings if f.is_stale]

    @property
    def auto_fixed(self) -> list[Correction]:
        return [c for c in self.corrections if c.action is RepairAction.AUTO_FIX and c.validation_passed]

    @property
    def drafts(self) -> list[Correction]:
        return [c for c in self.corrections if c.action is RepairAction.DRAFT_FIX]

    @property
    def flagged(self) -> list[Correction]:
        return [c for c in self.corrections if c.action is RepairAction.FLAG_ONLY]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "sections_checked": self.sections_checked,
            "verified_accurate": self.sections_checked - len(self.stale_findings),
            "stale_sections_found": len(self.stale_findings),
            "auto_fixed": len(self.auto_fixed),
            "drafts": len(self.drafts),
            "flagged": len(self.flagged),
            "findings": [f.to_dict() for f in self.findings],
            "corrections": [c.to_dict() for c in self.corrections],
        }


class Pipeline:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.code_parser = CodeParser(config)
        self.doc_parser = DocParser(config)
        self.linker = Linker(config)
        self.diff = DiffAnalyzer(config)
        self.checker = StalenessChecker(config)
        self.repairer = RepairEngine(config)

    # -- mapping -------------------------------------------------------------

    def build_mapping(self, persist: bool = True) -> Mapping:
        chunks = self.code_parser.parse_repo()
        sections = self.doc_parser.parse_repo()

        store = EmbeddingStore(self.config)
        store.index_chunks(chunks)
        store.index_sections(sections)

        links = self.linker.build_links(chunks, sections, store)
        mapping = Mapping(code_chunks=chunks, doc_sections=sections, links=links)

        if persist:
            self._save_mapping(mapping)
        return mapping

    def load_mapping(self) -> Optional[Mapping]:
        path = self.config.mapping_path
        if not path.exists():
            return None
        try:
            return Mapping.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load mapping: %s", exc)
            return None

    def _save_mapping(self, mapping: Mapping) -> None:
        path = self.config.mapping_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(mapping.to_dict(), indent=2), encoding="utf-8")
        logger.info("Wrote mapping to %s", path)

    # -- detection -----------------------------------------------------------

    def run(
        self,
        base_ref: Optional[str] = None,
        head_ref: str = "HEAD",
        mapping: Optional[Mapping] = None,
    ) -> PipelineReport:
        """Detect stale docs for changes between ``base_ref`` and ``head_ref``.

        If ``base_ref`` is None, the working tree is compared against HEAD.
        """
        mapping = mapping or self.load_mapping() or self.build_mapping()

        if base_ref is None:
            changes = self.diff.analyze_working_tree()
        else:
            changes = self.diff.analyze_refs(base_ref, head_ref)
        logger.info("Detected %d meaningful code change(s)", len(changes))

        return self._evaluate(changes, mapping)

    def _evaluate(self, changes: list[CodeChange], mapping: Mapping) -> PipelineReport:
        report = PipelineReport()
        evaluated: set[tuple[str, str]] = set()

        for change in changes:
            suspects = self._suspects(change, mapping)
            for section in suspects:
                key = (change.chunk_id, section.section_id)
                if key in evaluated:
                    continue
                evaluated.add(key)
                report.sections_checked += 1

                finding = self.checker.check(change, section)
                report.findings.append(finding)
                if not finding.is_stale:
                    continue

                correction = self.repairer.repair(finding, change, section)
                report.corrections.append(correction)

        logger.info(
            "Run complete: %d checked, %d stale, %d auto-fixed, %d drafts, %d flagged",
            report.sections_checked,
            len(report.stale_findings),
            len(report.auto_fixed),
            len(report.drafts),
            len(report.flagged),
        )
        return report

    def _suspects(self, change: CodeChange, mapping: Mapping) -> list[DocSection]:
        """All doc sections linked to the changed chunk."""
        sections = mapping.sections_for_chunk(change.chunk_id)
        # Also match by bare symbol so renamed-file chunk ids still resolve.
        if not sections:
            symbol = change.chunk_id.split("::")[-1]
            sections = [
                s for s in mapping.doc_sections
                if symbol in s.code_references or symbol.split(".")[-1] in s.code_references
            ]
        return sections

    # -- live console --------------------------------------------------------

    def check_pasted(
        self,
        file_path: str,
        old_code: str,
        new_code: str,
        doc_heading: str,
        doc_content: str,
    ) -> dict[str, Any]:
        """Run the full staleness+repair logic on ad-hoc pasted input."""
        changes = self.diff.compare_sources(file_path, old_code, new_code)
        section = DocSection(
            section_id=f"{file_path}::{doc_heading}",
            file_path=file_path,
            heading_path=doc_heading,
            content=doc_content,
            code_references=self.doc_parser._extract_references(doc_content),  # noqa: SLF001
        )

        if not changes:
            return {
                "changes": [],
                "finding": None,
                "correction": None,
                "message": "No meaningful code change detected.",
            }

        # Pick the most relevant change (the one the doc most plausibly covers).
        change = self._most_relevant(changes, section)
        finding = self.checker.check(change, section)
        correction = None
        if finding.is_stale:
            correction = self.repairer.repair(finding, change, section)

        return {
            "changes": [c.to_dict() for c in changes],
            "finding": finding.to_dict(),
            "correction": correction.to_dict() if correction else None,
        }

    # -- audit (no diff) -----------------------------------------------------

    def audit(self, code_path: str, code_text: str, docs_text: str) -> dict[str, Any]:
        """Audit docs against the *current* code (single snapshot, no diff).

        Parses the supplied code and documentation, links them, and reports doc
        sections that contradict the code. Powers the dashboard's upload mode.
        """
        from .auditor import Auditor
        from .embeddings import EmbeddingStore

        chunks = self.code_parser.parse_source(code_path, code_text)
        sections = self.doc_parser.parse_text_loose("uploaded_docs.md", docs_text)

        store = EmbeddingStore(self.config)
        store.index_chunks(chunks)
        store.index_sections(sections)
        links = self.linker.build_links(chunks, sections, store)
        mapping = Mapping(code_chunks=chunks, doc_sections=sections, links=links)

        report = Auditor(self.config).audit(mapping)
        result = report.to_dict()
        result["code_chunks"] = len(chunks)
        result["doc_sections"] = len(sections)
        result["links"] = len(links)
        # How many doc sections actually reference this code (and were thus
        # auditable). Zero means the docs and code are unrelated — there was
        # nothing to compare, which is NOT the same as "consistent".
        result["auditable_sections"] = len({l.doc_section_id for l in links})
        return result

    @staticmethod
    def _most_relevant(changes: list[CodeChange], section: DocSection) -> CodeChange:
        refs = {r.lower() for r in section.code_references}
        content = section.content.lower()

        def score(change: CodeChange) -> int:
            symbol = change.chunk_id.split("::")[-1].split(".")[-1].lower()
            s = 0
            if symbol in refs:
                s += 3
            if symbol in content:
                s += 2
            if change.change_type in (ChangeType.API_SIGNATURE, ChangeType.CONFIG_CHANGE):
                s += 1
            return s

        return max(changes, key=score)
