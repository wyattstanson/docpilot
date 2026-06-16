"""FastAPI application exposing the DocPilot engine to the dashboard.

Endpoints (all under ``/api``):

* ``GET  /api/health``            -- liveness.
* ``GET  /api/overview``          -- hero stats, health orb, activity feed.
* ``GET  /api/mapping``           -- the code<->docs link graph.
* ``GET  /api/staleness``         -- detected stale sections (with diffs).
* ``GET  /api/prs``               -- DocPilot-generated PR activity.
* ``GET  /api/config``            -- current configuration.
* ``PUT  /api/config``            -- update configuration.
* ``GET  /api/demos``             -- list built-in demos.
* ``POST /api/demos/{name}``      -- run a demo through the real pipeline.
* ``POST /api/check/paste``       -- run staleness check on pasted input.
* ``POST /api/check/github``      -- fetch a PR diff and run the pipeline.

Run with: ``python -m docpilot.server`` (or ``uvicorn docpilot.server.app:app``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from ..core.config import Config
from ..core.pipeline import Pipeline
from ..demos import DEMOS, run_demo
from .store import DashboardStore

logger = logging.getLogger("docpilot.server")

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "FastAPI is required for the dashboard server. Install with "
        "`pip install fastapi uvicorn`."
    ) from exc


_DEMO_DESCRIPTIONS = {
    "renamed_param": "A function parameter was renamed; docs still cite the old name.",
    "changed_default": "A default value changed; docs still state the old default.",
    "removed_endpoint": "An API endpoint was removed but is still documented.",
    "new_config": "A new required config variable was added without documentation.",
}


class PasteRequest(BaseModel):
    file_path: str = "src/example.py"
    old_code: str
    new_code: str
    doc_heading: str = "Documentation"
    doc_content: str


class GithubRequest(BaseModel):
    repo_url: str
    pr_number: int


class ConfigUpdate(BaseModel):
    confidence_threshold: Optional[float] = None
    similarity_threshold: Optional[float] = None
    auto_merge: Optional[bool] = None
    llm_provider: Optional[str] = None


def create_app(config: Optional[Config] = None) -> "FastAPI":
    config = config or Config.load(repo_root=".")
    store = DashboardStore(config)
    pipeline = Pipeline(config)
    app = FastAPI(title="DocPilot Dashboard API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- API ----------------------------------------------------------------

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "provider": config.llm_provider, "model": config.resolved_llm_model()}

    @app.get("/api/overview")
    def overview() -> dict:
        return store.overview()

    @app.get("/api/staleness")
    def staleness() -> dict:
        return {"findings": store.findings()}

    @app.get("/api/prs")
    def prs() -> dict:
        return {"prs": store.prs()}

    @app.get("/api/mapping")
    def mapping() -> dict:
        m = pipeline.load_mapping()
        if m is None:
            return _demo_mapping()
        return {
            "code_chunks": [c.to_dict() for c in m.code_chunks],
            "doc_sections": [s.to_dict() for s in m.doc_sections],
            "links": [l.to_dict() for l in m.links],
        }

    @app.get("/api/config")
    def get_config() -> dict:
        return store.get_config()

    @app.put("/api/config")
    def put_config(update: ConfigUpdate) -> dict:
        return store.update_config({k: v for k, v in update.dict().items() if v is not None})

    @app.get("/api/demos")
    def list_demos() -> dict:
        return {
            "demos": [
                {"name": n, "description": _DEMO_DESCRIPTIONS.get(n, ""),
                 "file_path": DEMOS[n][0], "doc_heading": DEMOS[n][3]}
                for n in DEMOS
            ]
        }

    @app.post("/api/demos/{name}")
    def run_demo_endpoint(name: str) -> dict:
        if name not in DEMOS:
            raise HTTPException(status_code=404, detail=f"Unknown demo '{name}'")
        result = run_demo(name, config)
        store.record_live_check(name, result)
        return result

    @app.post("/api/check/paste")
    def check_paste(req: PasteRequest) -> dict:
        result = pipeline.check_pasted(
            req.file_path, req.old_code, req.new_code, req.doc_heading, req.doc_content
        )
        store.record_live_check(req.doc_heading, result)
        return result

    @app.post("/api/check/github")
    def check_github(req: GithubRequest) -> dict:
        try:
            return _run_github_check(config, pipeline, store, req)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc))

    # -- static dashboard (served when built) -------------------------------

    dist = Path(__file__).resolve().parent.parent.parent / "dashboard" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

        @app.get("/")
        def index() -> Any:
            return FileResponse(str(dist / "index.html"))

        @app.get("/{path:path}")
        def spa(path: str) -> Any:
            target = dist / path
            if target.is_file():
                return FileResponse(str(target))
            return FileResponse(str(dist / "index.html"))

    return app


def _run_github_check(config, pipeline, store, req: "GithubRequest") -> dict:
    """Fetch a PR's diff via PyGithub and run the pipeline over it."""
    try:
        from github import Github
    except ImportError:
        raise RuntimeError("PyGithub not installed; install with `pip install PyGithub`.")
    import os
    import re

    m = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)", req.repo_url)
    if not m:
        raise ValueError("Could not parse owner/repo from the URL.")
    full = f"{m.group(1)}/{m.group(2)}"
    gh = Github(os.environ.get("GITHUB_TOKEN"))
    repo = gh.get_repo(full)
    pr = repo.get_pull(req.pr_number)

    changes = []
    for f in pr.get_files():
        if f.patch is None:
            continue
        # Reconstruct old/new content from the raw blobs at base/head.
        try:
            old = repo.get_contents(f.filename, ref=pr.base.sha).decoded_content.decode("utf-8")
        except Exception:  # noqa: BLE001
            old = ""
        try:
            new = repo.get_contents(f.filename, ref=pr.head.sha).decoded_content.decode("utf-8")
        except Exception:  # noqa: BLE001
            new = ""
        changes.extend(c.to_dict() for c in pipeline.diff.compare_sources(f.filename, old, new))

    return {
        "repo": full,
        "pr_number": req.pr_number,
        "pr_title": pr.title,
        "changes": changes,
        "message": f"Analyzed PR #{req.pr_number}: {len(changes)} meaningful change(s).",
    }


def _demo_mapping() -> dict:
    """A small illustrative graph for the Repository Map before a build runs."""
    chunks = [
        {"chunk_id": "src/auth.py::verify_token", "symbol": "verify_token", "kind": "function", "file_path": "src/auth.py"},
        {"chunk_id": "src/config.py::REQUEST_TIMEOUT", "symbol": "REQUEST_TIMEOUT", "kind": "config", "file_path": "src/config.py"},
        {"chunk_id": "src/api.py::legacy_stats", "symbol": "legacy_stats", "kind": "api_route", "file_path": "src/api.py"},
        {"chunk_id": "src/config.py::REDIS_URL", "symbol": "REDIS_URL", "kind": "config", "file_path": "src/config.py"},
    ]
    sections = [
        {"section_id": "docs/auth.md::Authentication > Token Verification", "heading_path": "Authentication > Token Verification", "file_path": "docs/auth.md"},
        {"section_id": "docs/config.md::Configuration > Timeouts", "heading_path": "Configuration > Timeouts", "file_path": "docs/config.md"},
        {"section_id": "docs/api.md::API > Legacy Stats", "heading_path": "API > Legacy Stats", "file_path": "docs/api.md"},
        {"section_id": "docs/config.md::Configuration > Environment Variables", "heading_path": "Configuration > Environment Variables", "file_path": "docs/config.md"},
    ]
    links = [
        {"code_chunk_id": "src/auth.py::verify_token", "doc_section_id": sections[0]["section_id"], "link_type": "heuristic", "similarity_score": 1.0},
        {"code_chunk_id": "src/config.py::REQUEST_TIMEOUT", "doc_section_id": sections[1]["section_id"], "link_type": "heuristic", "similarity_score": 1.0},
        {"code_chunk_id": "src/api.py::legacy_stats", "doc_section_id": sections[2]["section_id"], "link_type": "heuristic", "similarity_score": 1.0},
        {"code_chunk_id": "src/config.py::REDIS_URL", "doc_section_id": sections[3]["section_id"], "link_type": "embedding", "similarity_score": 0.82},
    ]
    return {"code_chunks": chunks, "doc_sections": sections, "links": links}


# Module-level app for `uvicorn docpilot.server.app:app`.
app = create_app()
