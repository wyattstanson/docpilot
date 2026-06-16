"""Code and documentation parsing.

The parser walks a repository and produces two things:

* a list of :class:`~docpilot.core.models.CodeChunk` -- functions, classes,
  methods, API routes, config keys and CLI commands extracted from source;
* a list of :class:`~docpilot.core.models.DocSection` -- markdown split by
  heading hierarchy, each annotated with the code symbols it references.

Python is parsed precisely with :mod:`ast`. JavaScript/TypeScript is parsed
heuristically with regular expressions (no Node toolchain required). Parsing
never raises on a single bad file: failures are logged and skipped.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Iterable, Optional

from .config import Config
from .models import ChunkKind, CodeChunk, DocSection, Language

logger = logging.getLogger("docpilot.parser")

_PY_EXT = {".py"}
_JS_EXT = {".js", ".jsx", ".mjs", ".cjs"}
_TS_EXT = {".ts", ".tsx"}
_MD_EXT = {".md", ".markdown"}

# Decorator attribute names that denote an HTTP route (FastAPI/Flask).
_ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "route"}
# Decorator names that denote a CLI command (click/typer).
_CLI_DECORATORS = {"command", "group"}


def language_for(path: Path) -> Language:
    ext = path.suffix.lower()
    if ext in _PY_EXT:
        return Language.PYTHON
    if ext in _JS_EXT:
        return Language.JAVASCRIPT
    if ext in _TS_EXT:
        return Language.TYPESCRIPT
    if ext in _MD_EXT:
        return Language.MARKDOWN
    return Language.UNKNOWN


class CodeParser:
    """Extracts :class:`CodeChunk` objects from a repository."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.root = Path(config.repo_root).resolve()

    def parse_repo(self) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []
        for path in self._iter_code_files():
            try:
                chunks.extend(self.parse_file(path))
            except Exception as exc:  # noqa: BLE001 - never crash on one file
                logger.warning("Failed to parse %s: %s", path, exc)
        logger.info("Parsed %d code chunks", len(chunks))
        return chunks

    def parse_file(self, path: Path) -> list[CodeChunk]:
        lang = language_for(path)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Cannot read %s: %s", path, exc)
            return []
        return self.parse_source(self._rel(path), text, lang)

    def parse_source(
        self, rel: str, text: str, lang: Optional[Language] = None
    ) -> list[CodeChunk]:
        """Parse a chunk list from in-memory source (no filesystem access).

        Used by the diff analyzer to parse the *before* and *after* versions of
        a changed file, and by the live-testing console for pasted snippets.
        """
        if lang is None:
            lang = language_for(Path(rel))
        if lang is Language.PYTHON:
            return self._parse_python(rel, text)
        if lang in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            return self._parse_js_ts(rel, text, lang)
        return []

    # -- iteration -----------------------------------------------------------

    def _iter_code_files(self) -> Iterable[Path]:
        for spec in self.config.code_paths:
            base = (self.root / spec)
            if base.is_file():
                if language_for(base) is not Language.UNKNOWN:
                    yield base
                continue
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                if self._is_excluded(path):
                    continue
                if language_for(path) in (
                    Language.PYTHON,
                    Language.JAVASCRIPT,
                    Language.TYPESCRIPT,
                ):
                    yield path

    def _is_excluded(self, path: Path) -> bool:
        parts = set(path.parts)
        return any(ex in parts for ex in self.config.exclude_dirs)

    def _rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()

    # -- Python --------------------------------------------------------------

    def _parse_python(self, rel: str, text: str) -> list[CodeChunk]:
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            logger.warning("Python syntax error in %s: %s", rel, exc)
            return []
        lines = text.splitlines()
        chunks: list[CodeChunk] = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                chunks.append(self._py_function(rel, node, lines, parent=None))
            elif isinstance(node, ast.ClassDef):
                chunks.append(self._py_class(rel, node, lines))
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        chunks.append(self._py_function(rel, item, lines, parent=node.name))
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                cfg = self._py_config(rel, node, lines)
                if cfg:
                    chunks.append(cfg)

        # Module-level env var references become config chunks too.
        chunks.extend(self._py_env_vars(rel, text))
        return chunks

    def _py_function(
        self,
        rel: str,
        node: ast.AST,
        lines: list[str],
        parent: Optional[str],
    ) -> CodeChunk:
        name = node.name  # type: ignore[attr-defined]
        symbol = f"{parent}.{name}" if parent else name
        kind = ChunkKind.METHOD if parent else ChunkKind.FUNCTION
        metadata: dict = {"params": [a.arg for a in node.args.args]}  # type: ignore[attr-defined]

        route = self._py_route_decorator(node)
        if route:
            kind = ChunkKind.API_ROUTE
            metadata.update(route)
        elif self._py_has_cli_decorator(node):
            kind = ChunkKind.CLI_COMMAND

        start, end = self._span(node, lines)
        return CodeChunk(
            chunk_id=f"{rel}::{symbol}",
            file_path=rel,
            symbol=symbol,
            kind=kind,
            language=Language.PYTHON,
            source="\n".join(lines[start - 1 : end]),
            docstring=ast.get_docstring(node),  # type: ignore[arg-type]
            signature=self._py_signature(node),
            start_line=start,
            end_line=end,
            metadata=metadata,
        )

    def _py_class(self, rel: str, node: ast.ClassDef, lines: list[str]) -> CodeChunk:
        start, end = self._span(node, lines)
        bases = [self._name_of(b) for b in node.bases]
        return CodeChunk(
            chunk_id=f"{rel}::{node.name}",
            file_path=rel,
            symbol=node.name,
            kind=ChunkKind.CLASS,
            language=Language.PYTHON,
            source="\n".join(lines[start - 1 : end]),
            docstring=ast.get_docstring(node),
            signature=f"class {node.name}({', '.join(b for b in bases if b)})",
            start_line=start,
            end_line=end,
            metadata={"bases": [b for b in bases if b]},
        )

    def _py_config(
        self, rel: str, node: ast.AST, lines: list[str]
    ) -> Optional[CodeChunk]:
        """Treat UPPER_CASE module-level assignments as config keys."""
        targets: list[str] = []
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    targets.append(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets.append(node.target.id)
        const_names = [t for t in targets if t.isupper() and len(t) > 1]
        if not const_names:
            return None
        name = const_names[0]
        start, end = self._span(node, lines)
        return CodeChunk(
            chunk_id=f"{rel}::{name}",
            file_path=rel,
            symbol=name,
            kind=ChunkKind.CONFIG,
            language=Language.PYTHON,
            source="\n".join(lines[start - 1 : end]),
            start_line=start,
            end_line=end,
            metadata={"config_key": name},
        )

    def _py_env_vars(self, rel: str, text: str) -> list[CodeChunk]:
        """Capture os.environ / getenv references as config chunks."""
        chunks: list[CodeChunk] = []
        seen: set[str] = set()
        pattern = re.compile(
            r"""(?:os\.environ(?:\.get)?\(|getenv\()\s*['"]([A-Z][A-Z0-9_]+)['"]"""
        )
        for m in pattern.finditer(text):
            var = m.group(1)
            if var in seen:
                continue
            seen.add(var)
            line = text[: m.start()].count("\n") + 1
            chunks.append(
                CodeChunk(
                    chunk_id=f"{rel}::env:{var}",
                    file_path=rel,
                    symbol=var,
                    kind=ChunkKind.CONFIG,
                    language=Language.PYTHON,
                    source=m.group(0),
                    start_line=line,
                    end_line=line,
                    metadata={"env_var": var},
                )
            )
        return chunks

    @staticmethod
    def _span(node: ast.AST, lines: list[str]) -> tuple[int, int]:
        start = getattr(node, "lineno", 1)
        # Decorators sit above the def/class line; include them in the span so
        # the chunk source captures route/CLI decorators (and their paths).
        for dec in getattr(node, "decorator_list", []):
            start = min(start, getattr(dec, "lineno", start))
        end = getattr(node, "end_lineno", start) or start
        return start, min(end, len(lines))

    @staticmethod
    def _name_of(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    def _py_signature(self, node: ast.AST) -> str:
        try:
            args = node.args  # type: ignore[attr-defined]
            parts: list[str] = []
            defaults = list(args.defaults)
            pos = list(args.args)
            num_no_default = len(pos) - len(defaults)
            for i, a in enumerate(pos):
                if i >= num_no_default:
                    default = ast.unparse(defaults[i - num_no_default])
                    parts.append(f"{a.arg}={default}")
                else:
                    parts.append(a.arg)
            if args.vararg:
                parts.append(f"*{args.vararg.arg}")
            for a in args.kwonlyargs:
                parts.append(a.arg)
            if args.kwarg:
                parts.append(f"**{args.kwarg.arg}")
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            return f"{prefix} {node.name}({', '.join(parts)})"  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return getattr(node, "name", "")

    def _py_route_decorator(self, node: ast.AST) -> Optional[dict]:
        for dec in getattr(node, "decorator_list", []):
            call = dec if isinstance(dec, ast.Call) else None
            func = call.func if call else dec
            attr = func.attr if isinstance(func, ast.Attribute) else None
            if attr in _ROUTE_METHODS:
                path = None
                if call and call.args and isinstance(call.args[0], ast.Constant):
                    path = call.args[0].value
                method = "GET" if attr == "route" else attr.upper()
                # Flask passes methods= as a kwarg.
                if call:
                    for kw in call.keywords:
                        if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                            vals = [
                                e.value for e in kw.value.elts if isinstance(e, ast.Constant)
                            ]
                            if vals:
                                method = vals[0]
                return {"route": path, "method": method}
        return None

    def _py_has_cli_decorator(self, node: ast.AST) -> bool:
        for dec in getattr(node, "decorator_list", []):
            func = dec.func if isinstance(dec, ast.Call) else dec
            attr = func.attr if isinstance(func, ast.Attribute) else None
            name = func.id if isinstance(func, ast.Name) else None
            if attr in _CLI_DECORATORS or name in _CLI_DECORATORS:
                return True
        return False

    # -- JavaScript / TypeScript --------------------------------------------

    def _parse_js_ts(self, rel: str, text: str, lang: Language) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []
        seen: set[str] = set()

        def add(symbol: str, kind: ChunkKind, source: str, line: int, meta: dict | None = None):
            cid = f"{rel}::{symbol}"
            if cid in seen:
                return
            seen.add(cid)
            chunks.append(
                CodeChunk(
                    chunk_id=cid,
                    file_path=rel,
                    symbol=symbol,
                    kind=kind,
                    language=lang,
                    source=source.strip(),
                    start_line=line,
                    end_line=line + source.count("\n"),
                    metadata=meta or {},
                )
            )

        def line_at(pos: int) -> int:
            return text[:pos].count("\n") + 1

        # function declarations: function foo(...) / export function foo(...)
        for m in re.finditer(
            r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)",
            text,
        ):
            add(
                m.group(1),
                ChunkKind.FUNCTION,
                m.group(0),
                line_at(m.start()),
                {"params": _js_params(m.group(2))},
            )

        # arrow / function expressions: const foo = (...) => / = function(...)
        for m in re.finditer(
            r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
            r"(?:async\s+)?\(([^)]*)\)\s*=>",
            text,
        ):
            add(
                m.group(1),
                ChunkKind.FUNCTION,
                m.group(0),
                line_at(m.start()),
                {"params": _js_params(m.group(2))},
            )

        # classes: class Foo / export class Foo extends Bar
        for m in re.finditer(
            r"(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)"
            r"(?:\s+extends\s+([A-Za-z_$][\w$.]*))?",
            text,
        ):
            meta = {"extends": m.group(2)} if m.group(2) else {}
            add(m.group(1), ChunkKind.CLASS, m.group(0), line_at(m.start()), meta)

        # express routes: app.get('/path', ...) / router.post("/x", ...)
        for m in re.finditer(
            r"""(?:app|router)\.(get|post|put|patch|delete|use)\s*\(\s*['"`]([^'"`]+)['"`]""",
            text,
        ):
            method, route = m.group(1).upper(), m.group(2)
            add(
                f"{method} {route}",
                ChunkKind.API_ROUTE,
                m.group(0),
                line_at(m.start()),
                {"route": route, "method": method},
            )

        return chunks


def _js_params(raw: str) -> list[str]:
    params = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        # strip default values and type annotations
        name = re.split(r"[:=]", part)[0].strip().lstrip("{").rstrip("}").strip()
        name = name.lstrip(".")  # rest params
        if name:
            params.append(name)
    return params


class DocParser:
    """Splits markdown docs into heading-scoped :class:`DocSection` objects."""

    _HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
    # Inline code spans `like_this`, plus bare identifiers that look like symbols.
    _INLINE_CODE = re.compile(r"`([^`]+)`")
    _IDENTIFIER = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\b")
    _ROUTE = re.compile(r"`?((?:GET|POST|PUT|PATCH|DELETE)\s+)?(/[A-Za-z0-9_{}/:.-]+)`?")

    def __init__(self, config: Config) -> None:
        self.config = config
        self.root = Path(config.repo_root).resolve()

    def parse_repo(self) -> list[DocSection]:
        sections: list[DocSection] = []
        for path in self._iter_doc_files():
            try:
                sections.extend(self.parse_file(path))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to parse doc %s: %s", path, exc)
        logger.info("Parsed %d doc sections", len(sections))
        return sections

    def parse_file(self, path: Path) -> list[DocSection]:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Cannot read doc %s: %s", path, exc)
            return []
        rel = self._rel(path)
        return self.parse_text(rel, text)

    def parse_text(self, rel: str, text: str) -> list[DocSection]:
        lines = text.splitlines()
        sections: list[DocSection] = []
        # Stack of (level, heading) tracking the current heading path.
        stack: list[tuple[int, str]] = []
        cur_start = 0
        cur_lines: list[str] = []
        cur_heading_path = ""
        cur_level = 0

        def flush(end_line: int) -> None:
            nonlocal cur_lines
            content = "\n".join(cur_lines).strip()
            if cur_heading_path and (content or True):
                sections.append(self._make_section(rel, cur_heading_path, content, cur_start, end_line, cur_level))
            cur_lines = []

        for i, line in enumerate(lines, start=1):
            m = self._HEADING.match(line)
            if m:
                # close the previous section
                if cur_heading_path:
                    flush(i - 1)
                level = len(m.group(1))
                heading = m.group(2).strip()
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, heading))
                cur_heading_path = " > ".join(h for _, h in stack)
                cur_level = level
                cur_start = i
            else:
                cur_lines.append(line)
        if cur_heading_path:
            flush(len(lines))
        return sections

    def _make_section(
        self, rel: str, heading_path: str, content: str, start: int, end: int, level: int
    ) -> DocSection:
        refs = self._extract_references(heading_path + "\n" + content)
        return DocSection(
            section_id=f"{rel}::{heading_path}",
            file_path=rel,
            heading_path=heading_path,
            content=content,
            code_references=refs,
            start_line=start,
            end_line=end,
            level=level,
        )

    def _extract_references(self, text: str) -> list[str]:
        refs: set[str] = set()
        # 1) Everything in inline code spans is a strong reference signal.
        for m in self._INLINE_CODE.finditer(text):
            token = m.group(1).strip()
            refs.add(token)
            # also split foo() -> foo, Class.method -> Class, method
            bare = re.sub(r"\(.*?\)", "", token)
            for part in re.split(r"[.\s]", bare):
                part = part.strip()
                if part and re.match(r"^[A-Za-z_][\w]*$", part):
                    refs.add(part)
        # 2) API routes mentioned in prose.
        for m in self._ROUTE.finditer(text):
            if m.group(2):
                method = (m.group(1) or "").strip()
                refs.add(f"{method} {m.group(2)}".strip())
                refs.add(m.group(2))
        return sorted(refs)

    def _iter_doc_files(self) -> Iterable[Path]:
        for spec in self.config.doc_paths:
            base = self.root / spec
            if base.is_file():
                if language_for(base) is Language.MARKDOWN:
                    yield base
                continue
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if path.is_file() and language_for(path) is Language.MARKDOWN:
                    if not any(ex in path.parts for ex in self.config.exclude_dirs):
                        yield path

    def _rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()
