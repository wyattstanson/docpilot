"""Tests for the no-diff documentation auditor (upload/audit mode)."""

from __future__ import annotations

from docpilot.core.pipeline import Pipeline


def test_audit_flags_renamed_param(mock_config):
    code = "def verify_token(token, account_id):\n    return account_id\n"
    docs = "# Auth\n\n## Token\n\nCall `verify_token(token, user_id)`; `user_id` is the subject.\n"
    r = Pipeline(mock_config).audit("src/auth.py", code, docs)
    assert r["inconsistent"] >= 1
    f = next(f for f in r["findings"] if f["kind"] == "mismatch")
    assert "user_id" in f["diagnosis"]
    assert "account_id" in (f["suggested_fix"] or "")


def test_audit_flags_changed_default(mock_config):
    code = "REQUEST_TIMEOUT = 60\n"
    docs = "# Config\n\n## Timeouts\n\nThe `REQUEST_TIMEOUT` defaults to 30 seconds.\n"
    r = Pipeline(mock_config).audit("src/config.py", code, docs)
    f = next(f for f in r["findings"] if "REQUEST_TIMEOUT" in f["diagnosis"])
    assert "60" in (f["suggested_fix"] or "")


def test_audit_passes_consistent_docs(mock_config):
    code = "def verify_token(token, user_id):\n    return user_id\n"
    docs = "# Auth\n\n## Token\n\nCall `verify_token(token, user_id)` to validate.\n"
    r = Pipeline(mock_config).audit("src/auth.py", code, docs)
    assert r["inconsistent"] == 0


def test_audit_unrelated_docs_report_no_overlap(mock_config):
    # Docs that reference nothing in the code must report "no overlap",
    # not a false "consistent".
    code = "def verify_token(token, account_id):\n    return account_id\n"
    docs = "# Banana Bread\n\n## Ingredients\n\nMix 3 bananas with flour and bake at 350.\n"
    r = Pipeline(mock_config).audit("svc.py", code, docs)
    assert r["auditable_sections"] == 0
    assert r["links"] == 0
    assert r["inconsistent"] == 0


def test_audit_loose_parsing_without_headings(mock_config):
    # PDF-style prose with no markdown headings still produces sections.
    code = "def verify_token(token, account_id):\n    return account_id\n"
    docs = "Call verify_token(token, user_id) to validate a JWT.\n\nThe user_id must match the subject.\n"
    r = Pipeline(mock_config).audit("src/auth.py", code, docs)
    assert r["doc_sections"] >= 1
