"""Git diff parsing and meaningful-change detection.

The analyzer compares the *before* and *after* versions of changed files,
maps each change to the code chunk it affects, and classifies whether the
change is *meaningful* to documentation.

It exposes three entry points:

* :meth:`DiffAnalyzer.analyze_refs` -- diff two git refs (PR base vs head).
* :meth:`DiffAnalyzer.analyze_working_tree` -- diff HEAD vs the working tree.
* :meth:`DiffAnalyzer.compare_sources` -- diff two in-memory file contents
  (used by tests and the live-testing console; no git required).

Meaningful changes (API signature, config, feature add/remove, behavior) are
returned; comment-only, whitespace-only and test-file changes are skipped.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

from .config import Config
from .models import ChangeType, CodeChange, CodeChunk, Language
from .parser import CodeParser, language_for

logger = logging.getLogger("docpilot.diff")

_TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)|(_test\.|\.test\.|\.spec\.|test_)")


def _is_test_file(path: str) -> bool:
    return bool(_TEST_PATH.search(path))


def _strip_python_comments(source: str) -> str:
    """Normalize Python source by removing comments and blank lines."""
    out = []
    for line in source.splitlines():
        line = re.sub(r"(?<!['\"])#.*$", "", line)  # naive; good enough for filtering
        if line.strip():
            out.append(line.strip())
    return "\n".join(out)


def _strip_js_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    out = []
    for line in source.splitlines():
        line = re.sub(r"//.*$", "", line)
        if line.strip():
            out.append(line.strip())
    return "\n".join(out)


def _normalize(source: str, lang: Language) -> str:
    if lang is Language.PYTHON:
        return _strip_python_comments(source)
    if lang in (Language.JAVASCRIPT, Language.TYPESCRIPT):
        return _strip_js_comments(source)
    return "\n".join(l.strip() for l in source.splitlines() if l.strip())


class DiffAnalyzer:
    """Detects meaningful code changes between two versions of a repo."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.root = Path(config.repo_root).resolve()
        self.parser = CodeParser(config)

    # -- git-backed entry points --------------------------------------------

    def analyze_refs(self, base_ref: str, head_ref: str = "HEAD") -> list[CodeChange]:
        files = self._changed_files(base_ref, head_ref)
        changes: list[CodeChange] = []
        for rel in files:
            old = self._git_show(base_ref, rel)
            new = self._git_show(head_ref, rel)
            changes.extend(self.compare_sources(rel, old, new))
        return changes

    def analyze_working_tree(self, base_ref: str = "HEAD") -> list[CodeChange]:
        files = self._changed_files(base_ref, None)
        changes: list[CodeChange] = []
        for rel in files:
            old = self._git_show(base_ref, rel)
            new = self._read_working(rel)
            changes.extend(self.compare_sources(rel, old, new))
        return changes

    # -- core comparison (no git) -------------------------------------------

    def compare_sources(
        self, rel: str, old_text: Optional[str], new_text: Optional[str]
    ) -> list[CodeChange]:
        """Compare two versions of a single file and classify changes."""
        lang = language_for(Path(rel))
        if lang not in (Language.PYTHON, Language.JAVASCRIPT, Language.TYPESCRIPT):
            return []
        if _is_test_file(rel):
            logger.debug("Skipping test file %s", rel)
            return []

        old_chunks = self._index(self.parser.parse_source(rel, old_text, lang)) if old_text else {}
        new_chunks = self._index(self.parser.parse_source(rel, new_text, lang)) if new_text else {}

        changes: list[CodeChange] = []
        all_symbols = set(old_chunks) | set(new_chunks)
        for symbol in sorted(all_symbols):
            old_c = old_chunks.get(symbol)
            new_c = new_chunks.get(symbol)
            change = self._classify(rel, symbol, old_c, new_c, lang)
            if change is not None:
                changes.append(change)
        return changes

    def _classify(
        self,
        rel: str,
        symbol: str,
        old_c: Optional[CodeChunk],
        new_c: Optional[CodeChunk],
        lang: Language,
    ) -> Optional[CodeChange]:
        ref = new_c or old_c
        assert ref is not None
        chunk_id = ref.chunk_id

        if old_c is None and new_c is not None:
            return CodeChange(
                chunk_id=chunk_id,
                file_path=rel,
                change_type=ChangeType.FEATURE_ADDED,
                old_source=None,
                new_source=new_c.source,
                summary=f"New {new_c.kind.value} `{symbol}` added.",
            )
        if new_c is None and old_c is not None:
            return CodeChange(
                chunk_id=chunk_id,
                file_path=rel,
                change_type=ChangeType.FEATURE_REMOVED,
                old_source=old_c.source,
                new_source=None,
                summary=f"{old_c.kind.value.capitalize()} `{symbol}` removed.",
            )

        assert old_c is not None and new_c is not None
        # Signature change?
        if (old_c.signature or "") != (new_c.signature or ""):
            return CodeChange(
                chunk_id=chunk_id,
                file_path=rel,
                change_type=ChangeType.API_SIGNATURE,
                old_source=old_c.source,
                new_source=new_c.source,
                summary=(
                    f"Signature of `{symbol}` changed: "
                    f"`{old_c.signature}` -> `{new_c.signature}`"
                ),
            )
        # Config default change?
        if old_c.kind.value == "config" and old_c.source.strip() != new_c.source.strip():
            return CodeChange(
                chunk_id=chunk_id,
                file_path=rel,
                change_type=ChangeType.CONFIG_CHANGE,
                old_source=old_c.source,
                new_source=new_c.source,
                summary=f"Config `{symbol}` changed.",
            )
        # Body change ignoring comments/whitespace -> behavior change.
        if _normalize(old_c.source, lang) != _normalize(new_c.source, lang):
            return CodeChange(
                chunk_id=chunk_id,
                file_path=rel,
                change_type=ChangeType.BEHAVIOR_CHANGE,
                old_source=old_c.source,
                new_source=new_c.source,
                summary=f"Behavior of `{symbol}` changed.",
            )
        # Only comments/whitespace differ -> not meaningful.
        return None

    @staticmethod
    def _index(chunks: list[CodeChunk]) -> dict[str, CodeChunk]:
        return {c.symbol: c for c in chunks}

    # -- git plumbing --------------------------------------------------------

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            logger.debug("git %s failed: %s", " ".join(args), result.stderr.strip())
            return ""
        return result.stdout

    def _changed_files(self, base_ref: str, head_ref: Optional[str]) -> list[str]:
        args = ["diff", "--name-only", base_ref]
        if head_ref:
            args.append(head_ref)
        out = self._git(*args)
        files = [f.strip() for f in out.splitlines() if f.strip()]
        return [f for f in files if language_for(Path(f)) in (
            Language.PYTHON, Language.JAVASCRIPT, Language.TYPESCRIPT
        )]

    def _git_show(self, ref: str, rel: str) -> Optional[str]:
        out = self._git("show", f"{ref}:{rel}")
        return out if out else None

    def _read_working(self, rel: str) -> Optional[str]:
        path = self.root / rel
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
