"""Tests for the staleness checker (heuristic / offline path)."""

from __future__ import annotations

from docpilot.core.diff_analyzer import DiffAnalyzer
from docpilot.core.models import Confidence, DocSection
from docpilot.core.staleness_checker import StalenessChecker


def _section(content: str, refs: list[str]) -> DocSection:
    return DocSection(
        section_id="docs/a.md::S",
        file_path="docs/a.md",
        heading_path="S",
        content=content,
        code_references=refs,
    )


def test_renamed_param_flagged_high(mock_config):
    change = DiffAnalyzer(mock_config).compare_sources(
        "src/a.py", "def f(user_id):\n    return user_id\n", "def f(account_id):\n    return account_id\n"
    )[0]
    section = _section("Pass `user_id` to identify the caller.", ["user_id", "f"])
    finding = StalenessChecker(mock_config).check(change, section)
    assert finding.is_stale
    assert finding.confidence is Confidence.HIGH


def test_changed_default_flagged_high(mock_config):
    change = DiffAnalyzer(mock_config).compare_sources(
        "src/config.py", "TIMEOUT = 30\n", "TIMEOUT = 60\n"
    )[0]
    section = _section("The `TIMEOUT` defaults to 30 seconds.", ["TIMEOUT"])
    finding = StalenessChecker(mock_config).check(change, section)
    assert finding.is_stale
    assert finding.confidence is Confidence.HIGH


def test_removed_feature_flagged(mock_config):
    change = DiffAnalyzer(mock_config).compare_sources(
        "src/a.py", "def legacy_stats():\n    return 1\n", ""
    )[0]
    section = _section("Call `legacy_stats` for old numbers.", ["legacy_stats"])
    finding = StalenessChecker(mock_config).check(change, section)
    assert finding.is_stale


def test_unrelated_doc_not_flagged(mock_config):
    change = DiffAnalyzer(mock_config).compare_sources(
        "src/a.py", "def f(user_id):\n    return user_id\n", "def f(account_id):\n    return account_id\n"
    )[0]
    section = _section("This section is about something else entirely.", ["other"])
    finding = StalenessChecker(mock_config).check(change, section)
    assert not finding.is_stale
