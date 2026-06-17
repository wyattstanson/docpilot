# DocPilot — Self-Healing Technical Documentation

[![Live Demo](https://img.shields.io/badge/Live%20Demo-dashboard-06b6d4)](https://docpilot-dashboard.onrender.com)
[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-DocPilot-7c3aed?logo=github)](https://github.com/marketplace/actions/docpilot-self-healing-docs)
[![Release](https://img.shields.io/github/v/release/wyattstanson/docpilot?color=7c3aed)](https://github.com/wyattstanson/docpilot/releases)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Tests](https://img.shields.io/badge/tests-36%20passing-brightgreen)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**🚀 [Live dashboard](https://docpilot-dashboard.onrender.com)** · **[Marketplace Action](https://github.com/marketplace/actions/docpilot-self-healing-docs)** · **[See it fix a real PR](https://github.com/wyattstanson/docpilot-demo/pull/1)**
> _(the live demo is on a free tier — the first load after idle takes ~50s to wake up)_

> Every engineering team has stale docs. DocPilot detects when a code change
> makes documentation inaccurate, pinpoints the exact stale section, and either
> opens a PR with a corrected version or flags it for human review — right
> inside your CI.

DocPilot is a CI/CD tool (packaged as a GitHub Action) built on the full AI
engineering stack: semantic code parsing, embeddings + retrieval, and LLM
generation behind a two-pass quality gate.

---

## How it works

```
                 ┌──────────────┐
   code + docs ─▶│   Parser     │─▶ code chunks  +  doc sections
                 └──────────────┘        │
                                         ▼
                 ┌──────────────┐   ┌──────────────┐
                 │  Embeddings  │──▶│   Linker     │─▶ .docpilot/mapping.json
                 │ (ChromaDB)   │   │ heuristic +  │   (the link graph)
                 └──────────────┘   │  embedding   │
                                    └──────────────┘
   git diff  ─▶  ┌──────────────┐         │
                 │ Diff Analyzer│─ meaningful changes ─┐
                 └──────────────┘                      ▼
                                            ┌────────────────────┐
                                            │ Staleness Checker  │  (LLM, pass 1)
                                            │  is it stale?      │
                                            └────────────────────┘
                                                      │ stale
                                                      ▼
                                            ┌────────────────────┐
                                            │   Repair Engine    │  (LLM, pass 2)
                                            │ rewrite + validate │
                                            └────────────────────┘
                                                      │
                            high → auto-fix PR   medium → draft   low → flag
```

### Pipeline stages

| Stage | Module | What it does |
|-------|--------|--------------|
| Parse code | [`core/parser.py`](docpilot/core/parser.py) | Extracts functions, classes, methods, API routes, config keys, env vars, CLI commands. Python via `ast`; JS/TS via robust regex. Stable ids `file::symbol`. |
| Parse docs | [`core/parser.py`](docpilot/core/parser.py) | Splits markdown by heading hierarchy; records the code symbols each section references. |
| Embed | [`core/embeddings.py`](docpilot/core/embeddings.py) | `text-embedding-3-small` into ChromaDB (file-based); in-memory fallback when Chroma isn't installed. |
| Link | [`core/linker.py`](docpilot/core/linker.py) | Heuristic links (symbol mentioned in prose) **+** embedding links (cosine ≥ threshold). Heuristic wins on ties. |
| Diff | [`core/diff_analyzer.py`](docpilot/core/diff_analyzer.py) | Maps a git diff to chunks; filters out comment/whitespace/test changes; classifies signature / config / feature / behavior changes. |
| Check | [`core/staleness_checker.py`](docpilot/core/staleness_checker.py) | LLM verifies whether each linked doc is *actually* stale (false-positive filter) with a confidence level. |
| Repair | [`core/repair_engine.py`](docpilot/core/repair_engine.py) | Rewrites only the stale parts, then a second LLM pass validates the fix. Confidence routing: auto-fix / draft / flag. |

### Runs offline by design

DocPilot **never** imports a vendor SDK at load time. With no API key it falls
back to deterministic *mock* providers — hashing-based embeddings and a
heuristic staleness/repair engine — so the full pipeline is runnable in tests
and CI without secrets. Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` to switch
to real models; nothing else changes.

---

## Install

```bash
pip install -e .            # core engine, zero required dependencies
pip install -e ".[all]"     # + openai, anthropic, chromadb, PyGithub
```

Requires Python 3.11+.

## CLI usage

```bash
# 1. Build the code-to-docs mapping (writes .docpilot/mapping.json)
docpilot build --code-paths src,lib --docs-paths docs,README.md

# 2. Inspect the link graph
docpilot graph

# 3. Detect stale docs for the working tree (or a pair of refs)
docpilot check                       # working tree vs HEAD
docpilot check --base main --head HEAD --json

# 4. Run a built-in staleness example end-to-end
docpilot demo renamed_param
```

## GitHub Action

DocPilot ships as a Docker-based Action (`action.yml` + `Dockerfile` at the repo
root; entrypoint in [`action/entrypoint.py`](docpilot/action/entrypoint.py)).
On every PR it builds/loads the mapping, diffs base→head, runs the pipeline, and
then routes by confidence:

| Confidence | Action |
|-----------|--------|
| **high** | Auto-fix: commit the corrected section to `docpilot/fix-<pr>-<ts>` and open a fix PR |
| **medium** | Draft fix: same, but wrapped in `<!-- DOCPILOT: REVIEW NEEDED -->` markers |
| **low** | Flag only: no code change; called out in the PR comment |

It posts a single, self-updating summary comment on the PR:

```
## 🛩️ DocPilot Report
| Metric | Count |
|--------|-------|
| Sections checked | 12 |
| Verified accurate | 9 |
| Auto-fixed | 1 |
| Flagged for review | 2 |

**Auto-fixed:** docs/auth.md#token-verification — see PR #42
**Needs review:** docs/config.md#environment-variables
```

Usage (consumer workflow — see [.github/workflows/docpilot.yml](.github/workflows/docpilot.yml)):

```yaml
- uses: actions/checkout@v4
  with: { fetch-depth: 0 }
- uses: wyattstanson/docpilot@v1
  with:
    llm_api_key: ${{ secrets.OPENAI_API_KEY }}
    llm_provider: openai
    docs_paths: "docs/,README.md"
    code_paths: "src/,lib/"
```

Required permissions: `contents: write` (push fix branches) and
`pull-requests: write` (open PRs / comment). With no token the entrypoint runs
in **dry-run** mode — it logs the PR/comment it *would* create — so you can test
locally with `python -m docpilot.action.entrypoint`.

Configuration resolves from `.docpilot/config.json` < environment
(`DOCPILOT_*`, `OPENAI_API_KEY`, …) < CLI flags. See
[`core/config.py`](docpilot/core/config.py).

---

## Accuracy

The four canonical staleness patterns, run through the **real** pipeline
(`docpilot demo <name>`, offline heuristic providers):

| Pattern | Demo | Detected | Confidence | Action | Diagnosis |
|---------|------|:--------:|:----------:|--------|-----------|
| Renamed parameter | `renamed_param` | ✅ | high | auto-fix ✓ validated | `user_id` → `account_id` in docs |
| Changed default | `changed_default` | ✅ | high | auto-fix ✓ validated | default `30` → `60` |
| Removed endpoint | `removed_endpoint` | ✅ | high | auto-fix ✓ validated | `/legacy/stats` still documented |
| New undocumented config | `new_config` | ✅ | medium | draft fix ✓ validated | `REDIS_URL` undocumented |

Negative controls (unrelated docs, comment-only / whitespace / test-file
changes) are correctly **not** flagged — see
[`tests/test_diff_analyzer.py`](tests/test_diff_analyzer.py) and
[`tests/test_staleness_checker.py`](tests/test_staleness_checker.py).

### Benchmark (Phase 5)

A labeled corpus of **18 realistic cases** — 11 positives (rename, default
change, removal, new config, added param, JS route removal …) and 7 negatives
(comment-only, whitespace, internal refactor, added private helper, test-file
change, unrelated doc, docstring polish) — is scored against ground-truth
labels by [`docpilot/benchmark`](docpilot/benchmark/runner.py). Run it yourself:

```bash
docpilot benchmark                       # uses your configured provider
python -m docpilot.benchmark --out RESULTS.md
```

Results in deterministic **mock** mode (offline, reproducible by anyone):

| Metric | Result | Target | Verdict |
|--------|--------|--------|---------|
| True-positive rate (recall) | **91%** (10/11) | > 85% | ✅ |
| False-positive rate | **0%** (0/7) | < 15% | ✅ |
| Precision | **100%** | — | — |
| Correction quality | **100%** (5 substitution fixes) | > 90% | ✅ |

The single miss is a **JS parameter rename** — a known limitation of the offline
heuristic (it has no JS signature model). With a real LLM provider that case is
**also caught**, since the model reasons over the before/after code directly.
Full report: [docpilot/benchmark/RESULTS.md](docpilot/benchmark/RESULTS.md).

> Correction quality is token-scored only on *substitution* fixes (renames,
> default changes) where the expected output is objectively defined; removal
> corrections are detection-only, since their ideal wording is subjective.

---

## Dashboard

A Netflix-grade dark monitoring UI (React + Tailwind + Vite) backed by a FastAPI
bridge to the engine. Six sections — Overview, Repository Map, Staleness Report,
PR Activity, Live Testing Console, Configuration — with glass-morphism cards,
micro-animations, skeleton loaders, toasts and keyboard nav (`Alt+1..6`).

The **Live Testing Console** runs the *real* pipeline in three modes: Paste (ad-hoc
diff + doc), GitHub (fetch a PR diff via PyGithub), and Demo (the four built-in
staleness patterns). The Overview/Staleness/PR pages are seeded from actual engine
output, not canned data.

```bash
# 1. Start the engine bridge (http://127.0.0.1:8000)
pip install fastapi uvicorn
python -m docpilot.server

# 2. Start the dashboard (http://localhost:5173, proxies /api to the bridge)
cd dashboard && npm install && npm run dev

# Production: `npm run build` emits dashboard/dist, which the FastAPI server
# serves directly at http://127.0.0.1:8000/.
```

The frontend falls back to representative sample data when the API is unreachable,
so it is always demonstrable.

## Testing

```bash
pip install -e ".[dev]"
pytest                          # 33 tests, all offline (mock providers)
```

---

## Project layout

```
docpilot/
  core/            parser, embeddings, linker, diff_analyzer,
                   staleness_checker, repair_engine, pipeline, config, llm
  prompts/         versioned LLM prompt templates (staleness / repair / validate)
  cli.py           command-line interface
  demos.py         pre-loaded examples that run the real pipeline
  action/          GitHub Action entrypoint (entrypoint.py)
  dashboard/       Netflix-style React + Tailwind monitoring UI            [phase 6]
action.yml         Action metadata (repo root, for the Marketplace)
Dockerfile         Action container (repo root)
.github/workflows/ example consumer workflow
tests/             parser, linker, diff, staleness, repair, applier,
                   report, integration, action
```

## Status

- [x] Code parser (Python / JS / TS / Markdown)
- [x] Embedding pipeline with ChromaDB persistence (+ offline fallback)
- [x] Link graph builder (heuristic + embedding)
- [x] Git diff analyzer with meaningful-change filter
- [x] LLM staleness checker with confidence scoring
- [x] Doc repair engine with validation pass
- [x] Confidence-based routing (auto-fix / draft / flag)
- [x] CLI + four end-to-end demos
- [x] Test suite (33 tests, fully offline)
- [x] GitHub Action (Dockerfile + action.yml + entrypoint)
- [x] PR workflow: fix branch + auto-PR, summary comment, confidence routing
- [x] FastAPI bridge exposing the engine to the dashboard
- [x] Netflix-style dashboard (6 sections) + Live Testing Console (paste/GitHub/demo)
- [x] Phase 5 accuracy benchmark (18-case labeled corpus, meets all targets)

---

## License

MIT
