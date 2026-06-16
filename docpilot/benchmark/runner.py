"""Run the benchmark corpus and compute accuracy metrics.

For each case the full pipeline runs via :meth:`Pipeline.check_pasted` (parse →
diff → staleness check → repair → validate). The detected verdict is compared
against the ground-truth label to build a confusion matrix, and corrections are
scored against expected tokens.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from ..core.config import Config
from ..core.pipeline import Pipeline
from .cases import CASES, BenchmarkCase

logger = logging.getLogger("docpilot.benchmark")

# Spec targets.
TARGET_TP_RATE = 0.85
TARGET_FP_RATE = 0.15
TARGET_QUALITY = 0.90


@dataclass
class CaseResult:
    case: BenchmarkCase
    detected_stale: bool
    confidence: Optional[str]
    outcome: str  # TP | FP | FN | TN
    correction_quality: Optional[bool]  # None if not applicable
    diagnosis: str = ""


@dataclass
class BenchmarkMetrics:
    results: list[CaseResult]

    @property
    def tp(self) -> int:
        return sum(1 for r in self.results if r.outcome == "TP")

    @property
    def fp(self) -> int:
        return sum(1 for r in self.results if r.outcome == "FP")

    @property
    def fn(self) -> int:
        return sum(1 for r in self.results if r.outcome == "FN")

    @property
    def tn(self) -> int:
        return sum(1 for r in self.results if r.outcome == "TN")

    @property
    def tp_rate(self) -> float:  # recall / sensitivity
        denom = self.tp + self.fn
        return self.tp / denom if denom else 1.0

    @property
    def fp_rate(self) -> float:
        denom = self.fp + self.tn
        return self.fp / denom if denom else 0.0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 1.0

    @property
    def correction_quality(self) -> float:
        scored = [r for r in self.results if r.correction_quality is not None]
        if not scored:
            return 1.0
        return sum(1 for r in scored if r.correction_quality) / len(scored)

    @property
    def corrections_scored(self) -> int:
        return sum(1 for r in self.results if r.correction_quality is not None)

    @property
    def passes_targets(self) -> bool:
        return (
            self.tp_rate >= TARGET_TP_RATE
            and self.fp_rate <= TARGET_FP_RATE
            and self.correction_quality >= TARGET_QUALITY
        )


def _score_correction(case: BenchmarkCase, correction: Optional[dict]) -> Optional[bool]:
    """Objectively score a correction against expected/forbidden tokens."""
    if not (case.expect_present or case.expect_absent):
        return None  # nothing to score for this case
    if not correction or not correction.get("corrected_content"):
        return False  # we expected a checkable fix but got none
    text = correction["corrected_content"]
    if any(tok not in text for tok in case.expect_present):
        return False
    if any(tok in text for tok in case.expect_absent):
        return False
    return True


def run_case(pipeline: Pipeline, case: BenchmarkCase) -> CaseResult:
    try:
        result = pipeline.check_pasted(
            case.file_path, case.old_code, case.new_code, case.doc_heading, case.doc_content
        )
    except Exception as exc:  # noqa: BLE001 - one bad case must not abort the run
        logger.warning("Case %s raised: %s", case.name, exc)
        result = {"finding": None, "correction": None}

    finding = result.get("finding")
    detected = bool(finding and finding.get("is_stale"))

    if case.expected_stale and detected:
        outcome = "TP"
    elif not case.expected_stale and detected:
        outcome = "FP"
    elif case.expected_stale and not detected:
        outcome = "FN"
    else:
        outcome = "TN"

    quality = _score_correction(case, result.get("correction")) if outcome == "TP" else None

    return CaseResult(
        case=case,
        detected_stale=detected,
        confidence=(finding or {}).get("confidence"),
        outcome=outcome,
        correction_quality=quality,
        diagnosis=(finding or {}).get("diagnosis", ""),
    )


def run_benchmark(config: Optional[Config] = None) -> BenchmarkMetrics:
    config = config or Config.load(repo_root=".")
    pipeline = Pipeline(config)
    results = [run_case(pipeline, c) for c in CASES]
    return BenchmarkMetrics(results=results)


# ── reporting ───────────────────────────────────────────────────────────────

def _check(value: float, target: float, lower_is_better: bool = False) -> str:
    ok = value <= target if lower_is_better else value >= target
    return "PASS" if ok else "FAIL"


def format_report(metrics: BenchmarkMetrics, provider: str) -> str:
    m = metrics
    lines = [
        "# DocPilot Accuracy Benchmark",
        "",
        f"Provider: **{provider}** · Corpus: **{len(m.results)}** labeled cases "
        f"({sum(1 for r in m.results if r.case.category == 'positive')} positive, "
        f"{sum(1 for r in m.results if r.case.category == 'negative')} negative)",
        "",
        "## Confusion matrix",
        "",
        "| | Predicted stale | Predicted fresh |",
        "|---|---|---|",
        f"| **Actually stale** | {m.tp} (TP) | {m.fn} (FN) |",
        f"| **Actually fresh** | {m.fp} (FP) | {m.tn} (TN) |",
        "",
        "## Metrics vs targets",
        "",
        "| Metric | Result | Target | Verdict |",
        "|--------|--------|--------|---------|",
        f"| True-positive rate (recall) | {m.tp_rate:.0%} | > 85% | {_check(m.tp_rate, TARGET_TP_RATE)} |",
        f"| False-positive rate | {m.fp_rate:.0%} | < 15% | {_check(m.fp_rate, TARGET_FP_RATE, lower_is_better=True)} |",
        f"| Precision | {m.precision:.0%} | — | — |",
        f"| Correction quality ({m.corrections_scored} scored) | {m.correction_quality:.0%} | > 90% | {_check(m.correction_quality, TARGET_QUALITY)} |",
        "",
        f"**Overall: {'PASS — all targets met' if m.passes_targets else 'FAIL — see above'}**",
        "",
        "## Per-case results",
        "",
        "| Case | Category | Expected | Detected | Outcome | Conf | Correction |",
        "|------|----------|----------|----------|---------|------|-----------|",
    ]
    for r in m.results:
        q = "—" if r.correction_quality is None else ("ok" if r.correction_quality else "poor")
        lines.append(
            f"| `{r.case.name}` | {r.case.category} | "
            f"{'stale' if r.case.expected_stale else 'fresh'} | "
            f"{'stale' if r.detected_stale else 'fresh'} | {r.outcome} | "
            f"{r.confidence or '—'} | {q} |"
        )
    # Note any honest misses.
    misses = [r for r in m.results if r.outcome in ("FN", "FP")]
    if misses:
        lines += ["", "## Known misses", ""]
        for r in misses:
            why = r.case.note or "(see case definition)"
            lines.append(f"- `{r.case.name}` ({r.outcome}): {why}")
    lines.append("")
    return "\n".join(lines)
