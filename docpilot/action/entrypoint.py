"""DocPilot GitHub Action entrypoint.

Reads inputs from ``INPUT_*`` environment variables (how ``actions`` passes
inputs) and the standard ``GITHUB_*`` context, runs the detection pipeline,
applies high/medium-confidence fixes to a new branch, opens a fix PR, comments
the summary on the triggering PR, and writes Action outputs.

Everything degrades to dry-run when secrets are absent, so the same code runs
locally for testing (`python -m docpilot.action.entrypoint`).
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

from ..core.applier import apply_corrections
from ..core.config import Config
from ..core.github_integration import GitHubIntegration, set_action_outputs
from ..core.pipeline import Pipeline, PipelineReport
from ..core.report_format import format_pr_comment

logger = logging.getLogger("docpilot.action")


def _input(name: str, default: str = "") -> str:
    """Read a GitHub Action input (``INPUT_<NAME>``), case-insensitively."""
    return os.environ.get(f"INPUT_{name.upper()}", default).strip()


def _bool_input(name: str, default: bool = False) -> bool:
    val = _input(name, str(default)).lower()
    return val in {"1", "true", "yes", "on"}


def _event() -> dict:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _resolve_refs(event: dict) -> tuple[Optional[str], str, Optional[int]]:
    """Return (base_ref, head_ref, pr_number) from the PR event context."""
    pr = event.get("pull_request") or {}
    pr_number = pr.get("number") or event.get("number")
    base = (pr.get("base") or {}).get("sha") or os.environ.get("GITHUB_BASE_REF")
    head = (pr.get("head") or {}).get("sha") or os.environ.get("GITHUB_SHA") or "HEAD"
    if base and not base.startswith("origin/") and "/" not in base and len(base) < 40:
        base = f"origin/{base}"  # branch name -> remote-tracking ref
    return base, head, pr_number


def build_config(repo_root: str) -> Config:
    overrides: dict = {}
    if _input("llm_provider"):
        overrides["llm_provider"] = _input("llm_provider")
    if _input("confidence_threshold"):
        overrides["confidence_threshold"] = float(_input("confidence_threshold"))
    if _input("docs_paths"):
        overrides["doc_paths"] = [p.strip() for p in _input("docs_paths").split(",")]
    if _input("code_paths"):
        overrides["code_paths"] = [p.strip() for p in _input("code_paths").split(",")]
    overrides["auto_merge"] = _bool_input("auto_merge", False)

    # The action passes the LLM key via INPUT_LLM_API_KEY; route to the provider.
    api_key = _input("llm_api_key")
    if api_key:
        provider = overrides.get("llm_provider", "openai")
        if provider == "anthropic":
            os.environ.setdefault("ANTHROPIC_API_KEY", api_key)
        else:
            os.environ.setdefault("OPENAI_API_KEY", api_key)
    return Config.load(repo_root=repo_root, **overrides)


def run(repo_root: Optional[str] = None) -> PipelineReport:
    repo_root = repo_root or os.environ.get("GITHUB_WORKSPACE", ".")
    config = build_config(repo_root)
    event = _event()
    base, head, pr_number = _resolve_refs(event)

    logger.info("DocPilot starting (base=%s head=%s pr=%s)", base, head, pr_number)
    pipeline = Pipeline(config)
    mapping = pipeline.load_mapping() or pipeline.build_mapping(persist=True)
    report = pipeline.run(base_ref=base, head_ref=head, mapping=mapping)

    repo_full = os.environ.get("GITHUB_REPOSITORY", "")
    repo_url = f"https://github.com/{repo_full}" if repo_full else ""
    gh = GitHubIntegration(repo_root=repo_root, repo_full_name=repo_full)

    fix_pr_url, fix_pr_number = "", None
    fixable = report.auto_fixed + report.drafts
    if fixable:
        applied = apply_corrections(report.corrections, mapping, repo_root, include_drafts=True)
        if applied:
            branch = f"docpilot/fix-{pr_number or 'wt'}-{int(time.time())}"
            files = sorted({a.file_path for a in applied})
            pr = gh.create_fix_pr(
                branch=branch,
                base=os.environ.get("GITHUB_BASE_REF", "main"),
                title=f"docs: DocPilot fixes for #{pr_number}" if pr_number else "docs: DocPilot fixes",
                body=_fix_pr_body(report, mapping, pr_number),
                files=files,
                commit_message=f"docs: auto-correct {len(applied)} stale section(s) via DocPilot",
            )
            fix_pr_url, fix_pr_number = pr.url, pr.number

    if pr_number is not None:
        comment = format_pr_comment(report, mapping, fix_pr_url, fix_pr_number, repo_url)
        gh.upsert_pr_comment(pr_number, comment)

    set_action_outputs(
        stale_sections_found=len(report.stale_findings),
        corrections_generated=len(report.corrections),
        pr_url=fix_pr_url,
    )
    return report


def _fix_pr_body(report: PipelineReport, mapping, pr_number) -> str:
    lines = [
        f"This PR was generated by **DocPilot** to fix documentation made stale "
        f"by {'#' + str(pr_number) if pr_number else 'recent changes'}.",
        "",
        "### Corrections",
    ]
    for c in report.auto_fixed + report.drafts:
        section = mapping.section_by_id(c.doc_section_id)
        heading = section.heading_path if section else c.doc_section_id
        lines.append(f"- **{heading}** ({c.action.value}, {c.confidence.value}): {c.diagnosis}")
    lines.append("")
    lines.append("Please review the changes before merging.")
    return "\n".join(lines)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        report = run()
    except Exception as exc:  # noqa: BLE001 - the Action must not hard-fail noisily
        logger.exception("DocPilot run failed: %s", exc)
        set_action_outputs(stale_sections_found=0, corrections_generated=0, pr_url="")
        return 0
    logger.info(
        "DocPilot done: %d stale, %d corrections.",
        len(report.stale_findings),
        len(report.corrections),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
