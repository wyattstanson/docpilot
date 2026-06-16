"""DocPilot command-line interface.

Commands
--------
``docpilot build``   Parse the repo and write ``.docpilot/mapping.json``.
``docpilot check``   Detect stale docs for a diff (refs or working tree).
``docpilot graph``   Print a summary of the code<->docs link graph.
``docpilot demo``    Run a built-in staleness example end-to-end.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .core.config import Config
from .core.pipeline import Pipeline


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _config_from_args(args: argparse.Namespace) -> Config:
    overrides: dict = {}
    if getattr(args, "code_paths", None):
        overrides["code_paths"] = [p.strip() for p in args.code_paths.split(",")]
    if getattr(args, "docs_paths", None):
        overrides["doc_paths"] = [p.strip() for p in args.docs_paths.split(",")]
    if getattr(args, "provider", None):
        overrides["llm_provider"] = args.provider
    if getattr(args, "threshold", None) is not None:
        overrides["confidence_threshold"] = args.threshold
    return Config.load(repo_root=args.repo, **overrides)


def cmd_build(args: argparse.Namespace) -> int:
    cfg = _config_from_args(args)
    pipeline = Pipeline(cfg)
    mapping = pipeline.build_mapping(persist=True)
    print(
        f"Built mapping: {len(mapping.code_chunks)} code chunks, "
        f"{len(mapping.doc_sections)} doc sections, {len(mapping.links)} links."
    )
    print(f"Saved to {cfg.mapping_path}")
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    cfg = _config_from_args(args)
    pipeline = Pipeline(cfg)
    mapping = pipeline.load_mapping() or pipeline.build_mapping(persist=False)
    print(f"Code chunks : {len(mapping.code_chunks)}")
    print(f"Doc sections: {len(mapping.doc_sections)}")
    print(f"Links       : {len(mapping.links)}")
    print("\nLinks:")
    for link in sorted(mapping.links, key=lambda l: l.code_chunk_id):
        marker = "H" if link.link_type.value == "heuristic" else "E"
        print(f"  [{marker}] {link.code_chunk_id}  <->  {link.doc_section_id}  ({link.similarity_score})")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    cfg = _config_from_args(args)
    pipeline = Pipeline(cfg)
    base = args.base if args.base else None
    report = pipeline.run(base_ref=base, head_ref=args.head)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    print("== DocPilot Report ==")
    print(f"Sections checked : {report.sections_checked}")
    print(f"Verified accurate: {report.sections_checked - len(report.stale_findings)}")
    print(f"Stale found      : {len(report.stale_findings)}")
    print(f"Auto-fixed       : {len(report.auto_fixed)}")
    print(f"Drafts           : {len(report.drafts)}")
    print(f"Flagged          : {len(report.flagged)}")
    for c in report.corrections:
        print(f"\n--- {c.doc_section_id} [{c.action.value}, {c.confidence.value}] ---")
        print(f"diagnosis: {c.diagnosis}")
        if c.corrected_content:
            print("corrected:")
            print(c.corrected_content)
    return 1 if report.stale_findings else 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    from .benchmark.runner import format_report, run_benchmark

    cfg = Config.load(repo_root=args.repo)
    metrics = run_benchmark(cfg)
    report = format_report(metrics, provider=cfg.llm_provider)
    print(report)
    if args.out:
        from pathlib import Path as _Path
        _Path(args.out).write_text(report, encoding="utf-8")
        print(f"\nWrote report to {args.out}")
    return 0 if metrics.passes_targets else 1


def cmd_demo(args: argparse.Namespace) -> int:
    from .demos import DEMOS, run_demo

    name = args.name
    if name not in DEMOS:
        print(f"Unknown demo '{name}'. Available: {', '.join(DEMOS)}")
        return 2
    cfg = Config.load(repo_root=args.repo)
    result = run_demo(name, cfg)
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="docpilot", description="Self-healing technical documentation engine.")
    p.add_argument("--repo", default=".", help="Repository root (default: cwd).")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="Build the code-to-docs mapping.")
    b.add_argument("--code-paths", dest="code_paths")
    b.add_argument("--docs-paths", dest="docs_paths")
    b.set_defaults(func=cmd_build)

    g = sub.add_parser("graph", help="Print the link graph.")
    g.add_argument("--code-paths", dest="code_paths")
    g.add_argument("--docs-paths", dest="docs_paths")
    g.set_defaults(func=cmd_graph)

    c = sub.add_parser("check", help="Detect stale docs for a diff.")
    c.add_argument("--base", default="", help="Base git ref. Omit to use the working tree.")
    c.add_argument("--head", default="HEAD", help="Head git ref (default: HEAD).")
    c.add_argument("--provider", choices=["openai", "anthropic", "mock"])
    c.add_argument("--threshold", type=float)
    c.add_argument("--json", action="store_true", help="Emit JSON.")
    c.set_defaults(func=cmd_check)

    d = sub.add_parser("demo", help="Run a built-in staleness example.")
    d.add_argument("name", help="Demo name (renamed_param, changed_default, removed_endpoint, new_config).")
    d.set_defaults(func=cmd_demo)

    bm = sub.add_parser("benchmark", help="Run the Phase 5 accuracy benchmark.")
    bm.add_argument("--out", help="Write the markdown report to this file.")
    bm.set_defaults(func=cmd_benchmark)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(args.verbose)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
