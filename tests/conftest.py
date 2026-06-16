"""Shared pytest fixtures for the DocPilot test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the package importable when running from a checkout without install.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from docpilot.core.config import Config  # noqa: E402


@pytest.fixture
def mock_config(tmp_path) -> Config:
    """A Config pinned to mock providers and an isolated temp repo root."""
    return Config.load(
        repo_root=str(tmp_path),
        llm_provider="mock",
        embedding_provider="mock",
    )
