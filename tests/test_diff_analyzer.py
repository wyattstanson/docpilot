"""Tests for the git diff analyzer and meaningful-change filter."""

from __future__ import annotations

from docpilot.core.diff_analyzer import DiffAnalyzer
from docpilot.core.models import ChangeType


def test_signature_change_detected(mock_config):
    da = DiffAnalyzer(mock_config)
    old = "def f(user_id):\n    return user_id\n"
    new = "def f(account_id):\n    return account_id\n"
    changes = da.compare_sources("src/a.py", old, new)
    assert len(changes) == 1
    assert changes[0].change_type is ChangeType.API_SIGNATURE


def test_comment_only_change_is_skipped(mock_config):
    da = DiffAnalyzer(mock_config)
    old = "def f(x):\n    return x\n"
    new = "def f(x):\n    # a new comment\n    return x\n"
    assert da.compare_sources("src/a.py", old, new) == []


def test_feature_added_and_removed(mock_config):
    da = DiffAnalyzer(mock_config)
    old = "def a():\n    return 1\n"
    new = "def a():\n    return 1\ndef b():\n    return 2\n"
    added = da.compare_sources("src/a.py", old, new)
    assert added[0].change_type is ChangeType.FEATURE_ADDED
    removed = da.compare_sources("src/a.py", new, old)
    assert removed[0].change_type is ChangeType.FEATURE_REMOVED


def test_config_default_change(mock_config):
    da = DiffAnalyzer(mock_config)
    changes = da.compare_sources("src/config.py", "TIMEOUT = 30\n", "TIMEOUT = 60\n")
    assert changes[0].change_type is ChangeType.CONFIG_CHANGE


def test_test_files_are_ignored(mock_config):
    da = DiffAnalyzer(mock_config)
    old = "def f(a):\n    return a\n"
    new = "def f(b):\n    return b\n"
    assert da.compare_sources("tests/test_a.py", old, new) == []


def test_behavior_change_detected(mock_config):
    da = DiffAnalyzer(mock_config)
    old = "def f(x):\n    return x + 1\n"
    new = "def f(x):\n    return x + 2\n"
    changes = da.compare_sources("src/a.py", old, new)
    assert changes[0].change_type is ChangeType.BEHAVIOR_CHANGE
