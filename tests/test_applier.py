"""Tests for splicing corrections back into doc files."""

from __future__ import annotations

from docpilot.core.applier import apply_corrections
from docpilot.core.config import Config
from docpilot.core.models import Confidence, Correction, RepairAction
from docpilot.core.parser import DocParser
from docpilot.core.models import Mapping


def _mapping_from_doc(cfg, rel, text):
    sections = DocParser(cfg).parse_text(rel, text)
    return Mapping(doc_sections=sections)


def test_apply_replaces_section_body(tmp_path):
    cfg = Config.load(repo_root=str(tmp_path), llm_provider="mock", embedding_provider="mock")
    md = "# Auth\n\n## Token\n\nPass `user_id` to verify.\n\n## Other\n\nUnrelated text.\n"
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "auth.md").write_text(md, encoding="utf-8")

    mapping = _mapping_from_doc(cfg, "docs/auth.md", md)
    section = next(s for s in mapping.doc_sections if s.heading_path == "Auth > Token")
    corr = Correction(
        doc_section_id=section.section_id,
        action=RepairAction.AUTO_FIX,
        original_content=section.content,
        corrected_content="Pass `account_id` to verify.",
        confidence=Confidence.HIGH,
        diagnosis="renamed",
        validation_passed=True,
    )

    applied = apply_corrections([corr], mapping, str(tmp_path))
    assert len(applied) == 1
    result = (tmp_path / "docs" / "auth.md").read_text(encoding="utf-8")
    assert "account_id" in result
    assert "user_id" not in result
    # Untouched section preserved.
    assert "Unrelated text." in result
    # Heading preserved.
    assert "## Token" in result


def test_flag_only_not_applied(tmp_path):
    cfg = Config.load(repo_root=str(tmp_path), llm_provider="mock", embedding_provider="mock")
    md = "# A\n\n## S\n\nbody\n"
    (tmp_path / "doc.md").write_text(md, encoding="utf-8")
    mapping = _mapping_from_doc(cfg, "doc.md", md)
    section = mapping.doc_sections[-1]
    corr = Correction(
        doc_section_id=section.section_id,
        action=RepairAction.FLAG_ONLY,
        original_content=section.content,
        corrected_content=None,
        confidence=Confidence.LOW,
        diagnosis="x",
    )
    assert apply_corrections([corr], mapping, str(tmp_path)) == []
