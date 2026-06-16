"""Apply generated corrections back into documentation files on disk.

A :class:`~docpilot.core.models.Correction` only carries the section id and the
corrected markdown body. To write it back we resolve the section's file path and
line range from the :class:`~docpilot.core.models.Mapping`, then splice the new
body in place of the old one.

Multiple corrections to the same file are applied bottom-up (highest start line
first) so earlier line numbers stay valid as later sections are rewritten.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .models import Correction, DocSection, Mapping, RepairAction

logger = logging.getLogger("docpilot.applier")


class AppliedFix:
    """Record of one correction written to disk."""

    def __init__(self, file_path: str, section_id: str, heading_path: str) -> None:
        self.file_path = file_path
        self.section_id = section_id
        self.heading_path = heading_path


def apply_corrections(
    corrections: list[Correction],
    mapping: Mapping,
    repo_root: str,
    include_drafts: bool = True,
) -> list[AppliedFix]:
    """Write applicable corrections into their doc files.

    Only ``AUTO_FIX`` (and, when ``include_drafts``, ``DRAFT_FIX``) corrections
    with non-empty corrected content are applied. Flags are never written.
    Returns the list of fixes actually applied.
    """
    root = Path(repo_root)
    # Group corrections by file, keeping a handle to the resolved section.
    by_file: dict[str, list[tuple[DocSection, Correction]]] = {}
    for corr in corrections:
        if not _should_apply(corr, include_drafts):
            continue
        section = mapping.section_by_id(corr.doc_section_id)
        if section is None:
            logger.warning("No section for correction %s; skipping.", corr.doc_section_id)
            continue
        by_file.setdefault(section.file_path, []).append((section, corr))

    applied: list[AppliedFix] = []
    for rel, items in by_file.items():
        path = root / rel
        if not path.exists():
            logger.warning("Doc file %s missing; skipping %d correction(s).", rel, len(items))
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Cannot read %s: %s", rel, exc)
            continue

        # Apply bottom-up so line indices remain valid.
        for section, corr in sorted(items, key=lambda x: x[0].start_line, reverse=True):
            new_lines = _splice(lines, section, corr.corrected_content or "")
            if new_lines is None:
                continue
            lines = new_lines
            applied.append(AppliedFix(rel, section.section_id, section.heading_path))

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("Applied %d correction(s) to %s", len(items), rel)

    return applied


def _should_apply(corr: Correction, include_drafts: bool) -> bool:
    if not corr.corrected_content:
        return False
    if corr.action is RepairAction.AUTO_FIX:
        return corr.validation_passed is not False
    if corr.action is RepairAction.DRAFT_FIX and include_drafts:
        return True
    return False


def _splice(lines: list[str], section: DocSection, new_body: str) -> Optional[list[str]]:
    """Replace the body of ``section`` (heading line excluded) with ``new_body``.

    The section spans ``start_line`` (the heading, 1-based) through
    ``end_line``; the body is everything after the heading line.
    """
    heading_idx = section.start_line - 1  # 0-based heading line
    body_start = heading_idx + 1
    body_end = section.end_line  # exclusive upper bound in 0-based slice terms
    if heading_idx < 0 or heading_idx >= len(lines):
        logger.warning("Section %s line range out of bounds; skipping.", section.section_id)
        return None
    body_end = min(body_end, len(lines))
    new_body_lines = new_body.splitlines()
    return lines[:body_start] + new_body_lines + lines[body_end:]
