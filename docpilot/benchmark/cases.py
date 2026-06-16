"""The labeled benchmark corpus.

Each :class:`BenchmarkCase` is a realistic before/after code change paired with
a documentation section and a *ground-truth* label:

* ``expected_stale`` -- should DocPilot flag this doc section as stale?
* ``expect_present`` / ``expect_absent`` -- tokens the corrected doc must /
  must not contain, used to score correction quality objectively.

The corpus mixes positives (changes that genuinely invalidate docs) with
negatives (comment/whitespace/refactor/test/unrelated changes that must NOT be
flagged) so false positives are measured, not just true positives. One case is
a deliberately hard miss (a JS parameter rename) to keep the benchmark honest.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BenchmarkCase:
    name: str
    category: str  # "positive" | "negative"
    file_path: str
    old_code: str
    new_code: str
    doc_heading: str
    doc_content: str
    expected_stale: bool
    expect_present: list[str] = field(default_factory=list)
    expect_absent: list[str] = field(default_factory=list)
    note: str = ""


CASES: list[BenchmarkCase] = [
    # ── positives ───────────────────────────────────────────────────────────
    BenchmarkCase(
        name="renamed_param",
        category="positive",
        file_path="src/auth.py",
        old_code="def verify_token(token, user_id):\n    return _decode(token, user_id)\n",
        new_code="def verify_token(token, account_id):\n    return _decode(token, account_id)\n",
        doc_heading="Authentication > Token Verification",
        doc_content="Call `verify_token(token, user_id)` to validate a JWT. The `user_id` "
        "argument must match the subject in the token.",
        expected_stale=True,
        expect_present=["account_id"],
        expect_absent=["user_id"],
    ),
    BenchmarkCase(
        name="changed_default_int",
        category="positive",
        file_path="src/config.py",
        old_code="REQUEST_TIMEOUT = 30\n",
        new_code="REQUEST_TIMEOUT = 60\n",
        doc_heading="Configuration > Timeouts",
        doc_content="The `REQUEST_TIMEOUT` setting defaults to 30 seconds.",
        expected_stale=True,
        expect_present=["60"],
        expect_absent=["30"],
    ),
    BenchmarkCase(
        name="changed_default_string",
        category="positive",
        file_path="src/config.py",
        old_code="HOST = 'localhost'\n",
        new_code="HOST = '0.0.0.0'\n",
        doc_heading="Configuration > Networking",
        doc_content="By default the server binds to `HOST` = localhost.",
        expected_stale=True,
        expect_present=["0.0.0.0"],
        expect_absent=["localhost"],
    ),
    BenchmarkCase(
        name="changed_default_pagesize",
        category="positive",
        file_path="src/config.py",
        old_code="PAGE_SIZE = 20\n",
        new_code="PAGE_SIZE = 50\n",
        doc_heading="API > Pagination",
        doc_content="Each page returns `PAGE_SIZE` results; the default is 20 per page.",
        expected_stale=True,
        expect_present=["50"],
        expect_absent=["20"],
    ),
    BenchmarkCase(
        name="removed_endpoint",
        category="positive",
        file_path="src/api.py",
        old_code='@router.get("/legacy/stats")\ndef legacy_stats():\n    return compute_legacy()\n',
        new_code="",
        doc_heading="API > Legacy Stats",
        doc_content="Send a `GET /legacy/stats` request to retrieve legacy statistics.",
        expected_stale=True,
    ),
    BenchmarkCase(
        name="removed_function",
        category="positive",
        file_path="src/users.py",
        old_code="def delete_user(user_id):\n    return _delete(user_id)\n",
        new_code="",
        doc_heading="Users > Deletion",
        doc_content="Use `delete_user(user_id)` to permanently remove an account.",
        expected_stale=True,
    ),
    BenchmarkCase(
        name="renamed_config_key",
        category="positive",
        file_path="src/config.py",
        old_code="MAX_RETRIES = 5\n",
        new_code="RETRY_LIMIT = 5\n",
        doc_heading="Configuration > Retries",
        doc_content="Set `MAX_RETRIES` to control how many times a request is retried.",
        expected_stale=True,
    ),
    BenchmarkCase(
        name="new_required_config",
        category="positive",
        file_path="src/config.py",
        old_code="DATABASE_URL = os.environ.get('DATABASE_URL')\n",
        new_code="DATABASE_URL = os.environ.get('DATABASE_URL')\n"
        "REDIS_URL = os.environ.get('REDIS_URL')\n",
        doc_heading="Configuration > Environment Variables",
        doc_content="Set the `DATABASE_URL` environment variable to point at Postgres. "
        "This is the only required setting.",
        expected_stale=True,
        expect_present=["REDIS_URL"],
    ),
    BenchmarkCase(
        name="added_required_param",
        category="positive",
        file_path="src/db.py",
        old_code="def connect(host):\n    return _open(host)\n",
        new_code="def connect(host, port):\n    return _open(host, port)\n",
        doc_heading="Database > Connecting",
        doc_content="Call `connect(host)` with the `host` argument to open a connection.",
        expected_stale=True,
        note="Flag-only expected (added param has no rename target).",
    ),
    BenchmarkCase(
        name="removed_route_js",
        category="positive",
        file_path="src/server.js",
        old_code='router.get("/v1/old", oldHandler);\n',
        new_code="",
        doc_heading="API > Old Endpoint",
        doc_content="Send `GET /v1/old` to fetch the legacy payload.",
        expected_stale=True,
    ),
    BenchmarkCase(
        name="renamed_param_js",
        category="positive",
        file_path="src/login.js",
        old_code="function login(user, password) { return auth(user, password); }\n",
        new_code="function login(account, password) { return auth(account, password); }\n",
        doc_heading="Auth > Login (JS)",
        doc_content="Call `login(user, password)`; the `user` argument is the username.",
        expected_stale=True,
        note="Hard case: JS parameter renames are not detected (known limitation).",
    ),
    # ── negatives ───────────────────────────────────────────────────────────
    BenchmarkCase(
        name="comment_only",
        category="negative",
        file_path="src/calc.py",
        old_code="def total(x):\n    return x * 2\n",
        new_code="def total(x):\n    # doubles the input\n    return x * 2\n",
        doc_heading="Math > Total",
        doc_content="`total(x)` returns twice the input value.",
        expected_stale=False,
    ),
    BenchmarkCase(
        name="whitespace_only",
        category="negative",
        file_path="src/calc.py",
        old_code="def total(x):\n    return x * 2\n",
        new_code="def total(x):\n\n    return x * 2   \n",
        doc_heading="Math > Total",
        doc_content="`total(x)` returns twice the input value.",
        expected_stale=False,
    ),
    BenchmarkCase(
        name="internal_refactor",
        category="negative",
        file_path="src/calc.py",
        old_code="def total(x):\n    result = x * 2\n    return result\n",
        new_code="def total(x):\n    doubled = x * 2\n    return doubled\n",
        doc_heading="Math > Total",
        doc_content="`total(x)` returns twice the input value.",
        expected_stale=False,
        note="Behavior unchanged; doc describes the contract, not internals.",
    ),
    BenchmarkCase(
        name="added_private_helper",
        category="negative",
        file_path="src/calc.py",
        old_code="def total(x):\n    return x * 2\n",
        new_code="def total(x):\n    return x * 2\ndef _round(v):\n    return round(v)\n",
        doc_heading="Math > Total",
        doc_content="`total(x)` returns twice the input value.",
        expected_stale=False,
    ),
    BenchmarkCase(
        name="test_file_change",
        category="negative",
        file_path="tests/test_calc.py",
        old_code="def test_total(a):\n    assert total(a)\n",
        new_code="def test_total(b):\n    assert total(b)\n",
        doc_heading="Math > Total",
        doc_content="`total(x)` returns twice the input value.",
        expected_stale=False,
    ),
    BenchmarkCase(
        name="unrelated_doc",
        category="negative",
        file_path="src/svc.py",
        old_code="def alpha(first):\n    return first\n",
        new_code="def alpha(second):\n    return second\n",
        doc_heading="Service > Beta",
        doc_content="Call `beta(x)` to compute the beta value for a record.",
        expected_stale=False,
        note="alpha's signature changed but the doc is about beta.",
    ),
    BenchmarkCase(
        name="docstring_polish",
        category="negative",
        file_path="src/calc.py",
        old_code='def total(x):\n    """Return twice x."""\n    return x * 2\n',
        new_code='def total(x):\n    """Return double the input x."""\n    return x * 2\n',
        doc_heading="Math > Total",
        doc_content="`total(x)` returns twice the input value.",
        expected_stale=False,
        note="Only the docstring wording changed; the contract is identical.",
    ),
]
