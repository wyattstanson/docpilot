"""The Phase 5 accuracy benchmark must meet the spec's targets in mock mode."""

from __future__ import annotations

from docpilot.benchmark.cases import CASES
from docpilot.benchmark.runner import (
    TARGET_FP_RATE,
    TARGET_QUALITY,
    TARGET_TP_RATE,
    run_benchmark,
)


def test_corpus_is_balanced():
    positives = [c for c in CASES if c.category == "positive"]
    negatives = [c for c in CASES if c.category == "negative"]
    assert len(positives) >= 8
    assert len(negatives) >= 5  # false positives are actually measured


def test_benchmark_meets_targets(mock_config):
    m = run_benchmark(mock_config)
    assert m.tp_rate >= TARGET_TP_RATE, f"recall {m.tp_rate:.2f} below target"
    assert m.fp_rate <= TARGET_FP_RATE, f"FP rate {m.fp_rate:.2f} above target"
    assert m.correction_quality >= TARGET_QUALITY, f"quality {m.correction_quality:.2f} below target"
    assert m.passes_targets


def test_no_false_positives_on_safe_changes(mock_config):
    m = run_benchmark(mock_config)
    fps = [r for r in m.results if r.outcome == "FP"]
    assert fps == [], f"unexpected false positives: {[r.case.name for r in fps]}"
