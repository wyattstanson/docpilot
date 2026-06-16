"""Tests for the repair engine (generation, validation, routing)."""

from __future__ import annotations

from docpilot.core.diff_analyzer import DiffAnalyzer
from docpilot.core.models import Confidence, DocSection, RepairAction
from docpilot.core.repair_engine import REVIEW_MARKER, RepairEngine
from docpilot.core.staleness_checker import StalenessChecker


def _section(content: str, refs: list[str]) -> DocSection:
    return DocSection(
        section_id="docs/a.md::S",
        file_path="docs/a.md",
        heading_path="S",
        content=content,
        code_references=refs,
    )


def test_renamed_param_autofixed(mock_config):
    change = DiffAnalyzer(mock_config).compare_sources(
        "src/a.py", "def f(user_id):\n    return user_id\n", "def f(account_id):\n    return account_id\n"
    )[0]
    section = _section("Pass `user_id` to identify the caller.", ["user_id"])
    finding = StalenessChecker(mock_config).check(change, section)
    correction = RepairEngine(mock_config).repair(finding, change, section)
    assert correction.action is RepairAction.AUTO_FIX
    assert "account_id" in correction.corrected_content
    assert "user_id" not in correction.corrected_content
    assert correction.validation_passed is True


def test_changed_default_autofixed(mock_config):
    change = DiffAnalyzer(mock_config).compare_sources(
        "src/config.py", "TIMEOUT = 30\n", "TIMEOUT = 60\n"
    )[0]
    section = _section("The `TIMEOUT` defaults to 30 seconds.", ["TIMEOUT"])
    finding = StalenessChecker(mock_config).check(change, section)
    correction = RepairEngine(mock_config).repair(finding, change, section)
    assert "60" in correction.corrected_content
    assert "30" not in correction.corrected_content


def test_low_confidence_is_flag_only(mock_config):
    change = DiffAnalyzer(mock_config).compare_sources(
        "src/a.py", "def f(x):\n    return x + 1\n", "def f(x):\n    return x + 2\n"
    )[0]
    section = _section("Describes behavior loosely.", ["f"])
    # Force a low-confidence finding.
    finding = StalenessChecker(mock_config).check(change, section)
    finding.is_stale = True
    finding.confidence = Confidence.LOW
    correction = RepairEngine(mock_config).repair(finding, change, section)
    assert correction.action is RepairAction.FLAG_ONLY
    assert correction.corrected_content is None


def test_medium_confidence_has_review_marker(mock_config):
    change = DiffAnalyzer(mock_config).compare_sources(
        "src/a.py", "def f(user_id):\n    return user_id\n", "def f(account_id):\n    return account_id\n"
    )[0]
    section = _section("Pass `user_id` to the call.", ["user_id"])
    finding = StalenessChecker(mock_config).check(change, section)
    finding.confidence = Confidence.MEDIUM
    correction = RepairEngine(mock_config).repair(finding, change, section)
    assert correction.action is RepairAction.DRAFT_FIX
    assert REVIEW_MARKER in correction.corrected_content
