"""Tests for the link graph builder."""

from __future__ import annotations

from docpilot.core.linker import Linker
from docpilot.core.models import Language, LinkType
from docpilot.core.parser import CodeParser, DocParser


def _build(mock_config):
    code = CodeParser(mock_config).parse_source(
        "src/auth.py",
        'def verify_token(token):\n    """Verify a JWT."""\n    return token\n',
        Language.PYTHON,
    )
    docs = DocParser(mock_config).parse_text(
        "docs/auth.md",
        "# Auth\n\n## Token\n\nUse `verify_token(token)` to validate a JWT.\n",
    )
    return code, docs


def test_heuristic_link_created(mock_config):
    code, docs = _build(mock_config)
    links = Linker(mock_config).build_links(code, docs)
    heuristic = [l for l in links if l.link_type is LinkType.HEURISTIC]
    assert any(
        l.code_chunk_id == "src/auth.py::verify_token" and "verify_token" == l.evidence
        for l in heuristic
    )


def test_heuristic_beats_embedding_on_same_pair(mock_config):
    code, docs = _build(mock_config)
    links = Linker(mock_config).build_links(code, docs)
    pair = [
        l for l in links
        if l.code_chunk_id == "src/auth.py::verify_token"
        and l.doc_section_id == "docs/auth.md::Auth > Token"
    ]
    assert len(pair) == 1
    assert pair[0].link_type is LinkType.HEURISTIC


def test_no_links_when_nothing_matches(mock_config):
    code = CodeParser(mock_config).parse_source(
        "src/x.py", "def alpha():\n    return 1\n", Language.PYTHON
    )
    docs = DocParser(mock_config).parse_text(
        "docs/y.md", "# Unrelated\n\nSomething about zebras and giraffes entirely.\n"
    )
    links = Linker(mock_config).build_links(code, docs)
    assert all(l.link_type is LinkType.EMBEDDING for l in links)
