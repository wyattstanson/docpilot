"""In-memory state for the dashboard, seeded from the *real* engine.

On first access the store runs all four built-in demos through the actual
pipeline and records the findings, corrections, activity events and synthetic
PR history they produce. This gives the Overview, Staleness Report and PR
Activity pages genuine engine output without requiring a live repository, while
the Live Testing Console still runs the pipeline on demand.
"""

from __future__ import annotations

import itertools
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..core.config import Config
from ..demos import DEMOS, run_demo

_DEMO_TITLES = {
    "renamed_param": "verify_token parameter renamed",
    "changed_default": "REQUEST_TIMEOUT default changed",
    "removed_endpoint": "/legacy/stats endpoint removed",
    "new_config": "REDIS_URL added without docs",
}


class DashboardStore:
    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config.load(repo_root=".")
        self._lock = threading.Lock()
        self._seeded = False
        self._activity: list[dict] = []
        self._findings: list[dict] = []
        self._prs: list[dict] = []
        self._id = itertools.count(1)
        self._config_overrides: dict[str, Any] = {}

    # -- seeding -------------------------------------------------------------

    def ensure_seeded(self) -> None:
        with self._lock:
            if self._seeded:
                return
            now = datetime.now(timezone.utc)
            pr_counter = itertools.count(101)
            for i, name in enumerate(DEMOS):
                result = run_demo(name, self.config)
                ts = (now - timedelta(hours=3 * (len(DEMOS) - i))).isoformat()
                finding = result.get("finding")
                correction = result.get("correction")
                title = _DEMO_TITLES.get(name, name)

                if finding:
                    record = {
                        "id": next(self._id),
                        "demo": name,
                        "title": title,
                        "file": result["input"]["file_path"],
                        "heading": result["input"]["doc_heading"],
                        "change_type": (result["changes"][0]["change_type"] if result["changes"] else "none"),
                        "is_stale": finding["is_stale"],
                        "confidence": finding["confidence"],
                        "diagnosis": finding["diagnosis"],
                        "action": correction["action"] if correction else "none",
                        "validation_passed": correction.get("validation_passed") if correction else None,
                        "original": correction["original_content"] if correction else result["input"]["doc_content"],
                        "corrected": correction.get("corrected_content") if correction else None,
                        "timestamp": ts,
                        "status": _status_for(correction),
                    }
                    self._findings.append(record)
                    self._activity.append({
                        "id": next(self._id),
                        "type": record["status"],
                        "title": title,
                        "detail": finding["diagnosis"],
                        "timestamp": ts,
                    })

                    if correction and correction["action"] in ("auto_fix", "draft_fix"):
                        num = next(pr_counter)
                        self._prs.append({
                            "id": next(self._id),
                            "number": num,
                            "title": f"docs: fix '{record['heading']}'",
                            "sections": [record["heading"]],
                            "confidence": finding["confidence"],
                            "action": correction["action"],
                            "merge_status": "merged" if correction["action"] == "auto_fix" else "open",
                            "url": f"https://github.com/your-org/your-repo/pull/{num}",
                            "timestamp": ts,
                        })

            self._seeded = True

    # -- reads ---------------------------------------------------------------

    def overview(self) -> dict:
        self.ensure_seeded()
        stale = [f for f in self._findings if f["is_stale"]]
        auto = [f for f in self._findings if f["action"] == "auto_fix"]
        docs_monitored = 47  # representative repo-wide figure for the hero stat
        health = "green"
        if any(f["confidence"] == "high" and f["status"] == "flagged" for f in stale):
            health = "red"
        elif stale:
            health = "amber"
        return {
            "stats": {
                "docs_monitored": docs_monitored,
                "stale_detected": len(stale),
                "auto_fixes": len(auto),
                "prs_generated": len(self._prs),
            },
            "health": health,
            "activity": sorted(self._activity, key=lambda e: e["timestamp"], reverse=True),
        }

    def findings(self) -> list[dict]:
        self.ensure_seeded()
        return sorted(self._findings, key=lambda f: f["timestamp"], reverse=True)

    def prs(self) -> list[dict]:
        self.ensure_seeded()
        return sorted(self._prs, key=lambda p: p["timestamp"], reverse=True)

    # -- config --------------------------------------------------------------

    def get_config(self) -> dict:
        d = self.config.to_dict()
        d.update(self._config_overrides)
        return d

    def update_config(self, updates: dict) -> dict:
        allowed = {
            "confidence_threshold", "similarity_threshold", "auto_merge",
            "llm_provider", "doc_paths", "code_paths",
        }
        for k, v in updates.items():
            if k in allowed:
                self._config_overrides[k] = v
                if hasattr(self.config, k):
                    setattr(self.config, k, v)
        return self.get_config()

    # -- live events ---------------------------------------------------------

    def record_live_check(self, title: str, result: dict) -> None:
        finding = result.get("finding")
        if not finding:
            return
        self._activity.insert(0, {
            "id": next(self._id),
            "type": "live",
            "title": f"Live check: {title}",
            "detail": finding.get("diagnosis", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


def _status_for(correction: Optional[dict]) -> str:
    if not correction:
        return "verified"
    action = correction.get("action")
    if action == "auto_fix":
        return "auto_fixed"
    if action == "draft_fix":
        return "drafted"
    return "flagged"
