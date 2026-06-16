"""Tests for the code and documentation parsers."""

from __future__ import annotations

from docpilot.core.models import ChunkKind, Language
from docpilot.core.parser import CodeParser, DocParser


def test_python_function_and_docstring(mock_config):
    parser = CodeParser(mock_config)
    src = '''def add(a, b=1):
    """Add two numbers."""
    return a + b
'''
    chunks = parser.parse_source("src/math.py", src, Language.PYTHON)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.chunk_id == "src/math.py::add"
    assert c.kind is ChunkKind.FUNCTION
    assert c.docstring == "Add two numbers."
    assert c.signature == "def add(a, b=1)"
    assert c.metadata["params"] == ["a", "b"]


def test_python_class_and_methods(mock_config):
    parser = CodeParser(mock_config)
    src = '''class Greeter:
    """Greets people."""
    def hello(self, name):
        return f"hi {name}"
'''
    chunks = parser.parse_source("src/g.py", src, Language.PYTHON)
    ids = {c.chunk_id: c for c in chunks}
    assert "src/g.py::Greeter" in ids
    assert "src/g.py::Greeter.hello" in ids
    assert ids["src/g.py::Greeter"].kind is ChunkKind.CLASS
    assert ids["src/g.py::Greeter.hello"].kind is ChunkKind.METHOD


def test_python_api_route_detection(mock_config):
    parser = CodeParser(mock_config)
    src = '''@router.get("/users/{id}")
def get_user(id):
    return id
'''
    chunks = parser.parse_source("src/api.py", src, Language.PYTHON)
    route = next(c for c in chunks if c.kind is ChunkKind.API_ROUTE)
    assert route.metadata["route"] == "/users/{id}"
    assert route.metadata["method"] == "GET"


def test_python_config_and_env(mock_config):
    parser = CodeParser(mock_config)
    src = "MAX_RETRIES = 5\nKEY = os.environ.get('API_KEY')\n"
    chunks = parser.parse_source("src/config.py", src, Language.PYTHON)
    kinds = {c.symbol: c.kind for c in chunks}
    assert kinds["MAX_RETRIES"] is ChunkKind.CONFIG
    assert kinds["API_KEY"] is ChunkKind.CONFIG


def test_js_function_and_route(mock_config):
    parser = CodeParser(mock_config)
    src = '''export function login(user, pass) { return true; }
app.post("/api/login", handler);
'''
    chunks = parser.parse_source("src/app.js", src, Language.JAVASCRIPT)
    symbols = {c.symbol for c in chunks}
    assert "login" in symbols
    assert "POST /api/login" in symbols


def test_doc_section_hierarchy_and_refs(mock_config):
    parser = DocParser(mock_config)
    md = """# API

## Authentication

Call `verify_token(token)` to validate a JWT.

## Limits

The `MAX_RETRIES` value defaults to 5.
"""
    sections = parser.parse_text("docs/api.md", md)
    paths = [s.heading_path for s in sections]
    assert "API > Authentication" in paths
    assert "API > Limits" in paths
    auth = next(s for s in sections if s.heading_path == "API > Authentication")
    assert "verify_token" in auth.code_references


def test_parser_does_not_crash_on_bad_python(mock_config):
    parser = CodeParser(mock_config)
    assert parser.parse_source("src/bad.py", "def (:\n", Language.PYTHON) == []
