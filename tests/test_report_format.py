"""Tests for the PR comment formatter."""

from __future__ import annotations

from docpilot.core.models import Confidence, Correction, DocSection, Mapping, RepairAction
from docpilot.core.pipeline import PipelineReport
from docpilot.core.report_format import format_pr_comment


def _report_with_autofix():
    section = DocSection(
        section_id="docs/auth.md::Auth > Token Verification",
        file_path="docs/auth.md",
        heading_path="Auth > Token Verification",
        content="body",
    )
    mapping = Mapping(doc_sections=[section])
    report = PipelineReport(sections_checked=12)
    report.corrections.append(
        Correction(
            doc_section_id=section.section_id,
            action=RepairAction.AUTO_FIX,
            original_content="body",
            corrected_content="fixed",
            confidence=Confidence.HIGH,
            diagnosis="renamed param",
            validation_passed=True,
        )
    )
    # Pad findings so "verified accurate" math is exercised.
    return report, mapping


def test_comment_has_metric_table_and_autofix():
    report, mapping = _report_with_autofix()
    out = format_pr_comment(report, mapping, fix_pr_number=42, repo_url="https://github.com/o/r")
    assert "## DocPilot Report" in out
    assert "| Sections checked | 12 |" in out
    assert "| Auto-fixed | 1 |" in out
    assert "see PR #42" in out
    assert "token-verification" in out  # anchor slug
    assert "renamed param" in out


def test_comment_all_clear():
    mapping = Mapping()
    report = PipelineReport(sections_checked=5)
    out = format_pr_comment(report, mapping)
    assert "up to date" in out
