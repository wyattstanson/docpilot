"""Run the accuracy benchmark: ``python -m docpilot.benchmark [--out FILE]``."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from ..core.config import Config
from .runner import format_report, run_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="DocPilot accuracy benchmark (Phase 5).")
    parser.add_argument("--repo", default=".", help="Repository root (for provider config).")
    parser.add_argument("--out", help="Write the markdown report to this file.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)
    config = Config.load(repo_root=args.repo)
    metrics = run_benchmark(config)
    report = format_report(metrics, provider=config.llm_provider)

    print(report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"\nWrote report to {args.out}")
    return 0 if metrics.passes_targets else 1


if __name__ == "__main__":
    raise SystemExit(main())
