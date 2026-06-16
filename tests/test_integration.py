"""End-to-end integration tests covering mapping + detection + demos."""

from __future__ import annotations

from docpilot.core.config import Config
from docpilot.core.pipeline import Pipeline
from docpilot.demos import DEMOS, run_demo


def _write(root, rel, content):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_mapping_links_code_to_docs(tmp_path):
    _write(tmp_path, "src/auth.py", 'def verify_token(token):\n    """Verify."""\n    return token\n')
    _write(tmp_path, "docs/auth.md", "# Auth\n\n## Token\n\nUse `verify_token(token)` to validate.\n")
    cfg = Config.load(repo_root=str(tmp_path), llm_provider="mock", embedding_provider="mock")
    mapping = Pipeline(cfg).build_mapping(persist=True)

    assert mapping.chunk_by_id("src/auth.py::verify_token") is not None
    assert any(l.code_chunk_id == "src/auth.py::verify_token" for l in mapping.links)
    assert cfg.mapping_path.exists()


def test_full_run_detects_renamed_param(tmp_path):
    _write(tmp_path, "src/auth.py", "def verify_token(token, user_id):\n    return user_id\n")
    _write(tmp_path, "docs/auth.md", "# Auth\n\n## Token\n\nPass `user_id` to `verify_token`.\n")
    cfg = Config.load(repo_root=str(tmp_path), llm_provider="mock", embedding_provider="mock")
    pipeline = Pipeline(cfg)
    mapping = pipeline.build_mapping(persist=False)

    # Simulate the new code by editing the source file, then diff vs the saved chunk.
    changes = pipeline.diff.compare_sources(
        "src/auth.py",
        "def verify_token(token, user_id):\n    return user_id\n",
        "def verify_token(token, account_id):\n    return account_id\n",
    )
    report = pipeline._evaluate(changes, mapping)
    assert report.sections_checked >= 1
    assert len(report.stale_findings) >= 1
    assert len(report.auto_fixed) >= 1


def test_all_demos_run(tmp_path):
    cfg = Config.load(repo_root=str(tmp_path), llm_provider="mock", embedding_provider="mock")
    for name in DEMOS:
        result = run_demo(name, cfg)
        assert "changes" in result
        assert result["demo"] == name


def test_demo_renamed_param_produces_fix(tmp_path):
    cfg = Config.load(repo_root=str(tmp_path), llm_provider="mock", embedding_provider="mock")
    result = run_demo("renamed_param", cfg)
    assert result["finding"]["is_stale"] is True
    assert result["correction"] is not None
    assert "account_id" in result["correction"]["corrected_content"]
