"""End-to-end test of the Action entrypoint against a real temp git repo.

Runs in dry-run mode (no GITHUB_TOKEN), so no network is touched, but the full
local flow executes: build mapping, diff working tree, detect staleness, apply
the fix, and create the fix branch locally.
"""

from __future__ import annotations

import os
import subprocess

import pytest

from docpilot.action import entrypoint
from docpilot.core.config import Config
from docpilot.core.pipeline import Pipeline


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _has_git() -> bool:
    return subprocess.run(["git", "--version"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _has_git(), reason="git not available")
def test_entrypoint_applies_fix_on_branch(tmp_path, monkeypatch):
    root = tmp_path
    (root / "src").mkdir()
    (root / "docs").mkdir()
    (root / "src" / "auth.py").write_text(
        "def verify_token(token, user_id):\n    return user_id\n", encoding="utf-8"
    )
    (root / "docs" / "auth.md").write_text(
        "# Auth\n\n## Token\n\nPass `user_id` to `verify_token` to validate.\n",
        encoding="utf-8",
    )

    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")

    # Build and persist the mapping from the committed state.
    cfg = Config.load(repo_root=str(root), llm_provider="mock", embedding_provider="mock")
    Pipeline(cfg).build_mapping(persist=True)

    # Make a stale-inducing change in the working tree.
    (root / "src" / "auth.py").write_text(
        "def verify_token(token, account_id):\n    return account_id\n", encoding="utf-8"
    )

    # Run the entrypoint in dry-run (no token), forcing mock providers.
    monkeypatch.setenv("GITHUB_WORKSPACE", str(root))
    monkeypatch.setenv("INPUT_LLM_PROVIDER", "mock")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

    report = entrypoint.run(repo_root=str(root))

    assert len(report.stale_findings) >= 1
    assert len(report.auto_fixed) >= 1

    # A fix branch should have been created and the doc updated on it.
    branches = _git(root, "branch", "--list", "docpilot/*").stdout
    assert "docpilot/fix-" in branches
    doc = (root / "docs" / "auth.md").read_text(encoding="utf-8")
    assert "account_id" in doc
    assert "user_id" not in doc
