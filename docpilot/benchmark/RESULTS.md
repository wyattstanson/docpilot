# DocPilot Accuracy Benchmark

Provider: **mock** · Corpus: **18** labeled cases (11 positive, 7 negative)

## Confusion matrix

| | Predicted stale | Predicted fresh |
|---|---|---|
| **Actually stale** | 10 (TP) | 1 (FN) |
| **Actually fresh** | 0 (FP) | 7 (TN) |

## Metrics vs targets

| Metric | Result | Target | Verdict |
|--------|--------|--------|---------|
| True-positive rate (recall) | 91% | > 85% | PASS |
| False-positive rate | 0% | < 15% | PASS |
| Precision | 100% | — | — |
| Correction quality (5 scored) | 100% | > 90% | PASS |

**Overall: PASS — all targets met**

## Per-case results

| Case | Category | Expected | Detected | Outcome | Conf | Correction |
|------|----------|----------|----------|---------|------|-----------|
| `renamed_param` | positive | stale | stale | TP | high | ok |
| `changed_default_int` | positive | stale | stale | TP | high | ok |
| `changed_default_string` | positive | stale | stale | TP | high | ok |
| `changed_default_pagesize` | positive | stale | stale | TP | high | ok |
| `removed_endpoint` | positive | stale | stale | TP | high | — |
| `removed_function` | positive | stale | stale | TP | high | — |
| `renamed_config_key` | positive | stale | stale | TP | high | — |
| `new_required_config` | positive | stale | stale | TP | medium | ok |
| `added_required_param` | positive | stale | stale | TP | medium | — |
| `removed_route_js` | positive | stale | stale | TP | high | — |
| `renamed_param_js` | positive | stale | fresh | FN | low | — |
| `comment_only` | negative | fresh | fresh | TN | — | — |
| `whitespace_only` | negative | fresh | fresh | TN | — | — |
| `internal_refactor` | negative | fresh | fresh | TN | low | — |
| `added_private_helper` | negative | fresh | fresh | TN | low | — |
| `test_file_change` | negative | fresh | fresh | TN | — | — |
| `unrelated_doc` | negative | fresh | fresh | TN | low | — |
| `docstring_polish` | negative | fresh | fresh | TN | low | — |

## Known misses

- `renamed_param_js` (FN): Hard case: JS parameter renames are not detected (known limitation).
