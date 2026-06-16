"""Pre-loaded staleness examples that exercise the *real* pipeline.

Each demo is a (file_path, old_code, new_code, doc_heading, doc_content) tuple
fed through :meth:`Pipeline.check_pasted`. Nothing here is canned: the parser,
diff analyzer, staleness checker and repair engine all run, so the output
reflects the engine's actual behavior.
"""

from __future__ import annotations

from typing import Any

from .core.config import Config
from .core.pipeline import Pipeline

# name -> (file_path, old_code, new_code, doc_heading, doc_content)
DEMOS: dict[str, tuple[str, str, str, str, str]] = {
    "renamed_param": (
        "src/auth.py",
        '''def verify_token(token, user_id):
    """Verify a JWT for the given user."""
    return _decode(token, user_id)
''',
        '''def verify_token(token, account_id):
    """Verify a JWT for the given account."""
    return _decode(token, account_id)
''',
        "Authentication > Token Verification",
        "Call `verify_token(token, user_id)` to validate a JWT. The `user_id` "
        "argument must match the subject encoded in the token, otherwise "
        "verification fails.",
    ),
    "changed_default": (
        "src/config.py",
        "REQUEST_TIMEOUT = 30\n",
        "REQUEST_TIMEOUT = 60\n",
        "Configuration > Timeouts",
        "The `REQUEST_TIMEOUT` setting controls how long the client waits for a "
        "response. It defaults to 30 seconds.",
    ),
    "removed_endpoint": (
        "src/api.py",
        '''@router.get("/legacy/stats")
def legacy_stats():
    """Return legacy statistics."""
    return compute_legacy()
''',
        "",
        "API > Legacy Stats",
        "Send a `GET /legacy/stats` request to retrieve legacy statistics. "
        "This endpoint returns aggregate counters for the dashboard.",
    ),
    "new_config": (
        "src/config.py",
        "DATABASE_URL = os.environ.get('DATABASE_URL')\n",
        "DATABASE_URL = os.environ.get('DATABASE_URL')\n"
        "REDIS_URL = os.environ.get('REDIS_URL')\n",
        "Configuration > Environment Variables",
        "Set `DATABASE_URL` to point DocPilot at your Postgres instance. "
        "This is the only required environment variable.",
    ),
}


def run_demo(name: str, config: Config | None = None) -> dict[str, Any]:
    config = config or Config.load(repo_root=".")
    pipeline = Pipeline(config)
    file_path, old, new, heading, content = DEMOS[name]
    result = pipeline.check_pasted(file_path, old, new, heading, content)
    result["demo"] = name
    result["input"] = {
        "file_path": file_path,
        "old_code": old,
        "new_code": new,
        "doc_heading": heading,
        "doc_content": content,
    }
    return result
