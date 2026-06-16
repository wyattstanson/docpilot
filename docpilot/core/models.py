"""Shared data models for the DocPilot engine.

These dataclasses are the lingua franca passed between the parser, linker,
diff analyzer, staleness checker, and repair engine. Every model is JSON
serializable via :meth:`to_dict` / :meth:`from_dict` so the full mapping can
be persisted to ``.docpilot/mapping.json``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class ChunkKind(str, enum.Enum):
    """The semantic category of a parsed code chunk."""

    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    API_ROUTE = "api_route"
    CONFIG = "config"
    CLI_COMMAND = "cli_command"
    MODULE = "module"


class Language(str, enum.Enum):
    """Languages the parser understands."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    MARKDOWN = "markdown"
    UNKNOWN = "unknown"


class LinkType(str, enum.Enum):
    """How a code<->doc link was established."""

    HEURISTIC = "heuristic"
    EMBEDDING = "embedding"


class Confidence(str, enum.Enum):
    """LLM confidence buckets used for routing decisions."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ChangeType(str, enum.Enum):
    """Classification of a meaningful code change."""

    API_SIGNATURE = "api_signature"
    CONFIG_CHANGE = "config_change"
    FEATURE_ADDED = "feature_added"
    FEATURE_REMOVED = "feature_removed"
    BEHAVIOR_CHANGE = "behavior_change"
    DOC_CHANGE = "doc_change"
    NONE = "none"


@dataclass
class CodeChunk:
    """A semantic unit of source code with a stable identifier.

    The ``chunk_id`` is ``"{file_path}::{symbol}"`` (e.g.
    ``"src/auth.py::verify_token"``) and is stable across runs so links and
    diffs can reference it reliably.
    """

    chunk_id: str
    file_path: str
    symbol: str
    kind: ChunkKind
    language: Language
    source: str
    docstring: Optional[str] = None
    signature: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    # Free-form, parser-supplied facts used for heuristic linking, e.g.
    # {"route": "/users/{id}", "method": "GET"} or {"params": ["a", "b"]}.
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["language"] = self.language.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CodeChunk":
        return cls(
            chunk_id=d["chunk_id"],
            file_path=d["file_path"],
            symbol=d["symbol"],
            kind=ChunkKind(d["kind"]),
            language=Language(d["language"]),
            source=d["source"],
            docstring=d.get("docstring"),
            signature=d.get("signature"),
            start_line=d.get("start_line", 0),
            end_line=d.get("end_line", 0),
            metadata=d.get("metadata", {}),
        )


@dataclass
class DocSection:
    """A documentation section split by markdown heading hierarchy."""

    section_id: str
    file_path: str
    heading_path: str
    content: str
    # Symbols referenced in the prose: function/class names, config keys,
    # CLI commands, API routes. Populated by the parser, consumed by the linker.
    code_references: list[str] = field(default_factory=list)
    start_line: int = 0
    end_line: int = 0
    level: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DocSection":
        return cls(
            section_id=d["section_id"],
            file_path=d["file_path"],
            heading_path=d["heading_path"],
            content=d["content"],
            code_references=d.get("code_references", []),
            start_line=d.get("start_line", 0),
            end_line=d.get("end_line", 0),
            level=d.get("level", 0),
        )


@dataclass
class Link:
    """A directed (but treated bidirectionally) link between code and a doc."""

    code_chunk_id: str
    doc_section_id: str
    link_type: LinkType
    similarity_score: float = 1.0
    # What in the prose triggered a heuristic link (the matched symbol).
    evidence: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["link_type"] = self.link_type.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Link":
        return cls(
            code_chunk_id=d["code_chunk_id"],
            doc_section_id=d["doc_section_id"],
            link_type=LinkType(d["link_type"]),
            similarity_score=d.get("similarity_score", 1.0),
            evidence=d.get("evidence"),
        )


@dataclass
class Mapping:
    """The complete code-to-docs graph persisted to ``mapping.json``."""

    version: str = "1.0"
    generated_at: str = field(default_factory=utc_now_iso)
    code_chunks: list[CodeChunk] = field(default_factory=list)
    doc_sections: list[DocSection] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "code_chunks": [c.to_dict() for c in self.code_chunks],
            "doc_sections": [s.to_dict() for s in self.doc_sections],
            "links": [l.to_dict() for l in self.links],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Mapping":
        return cls(
            version=d.get("version", "1.0"),
            generated_at=d.get("generated_at", utc_now_iso()),
            code_chunks=[CodeChunk.from_dict(c) for c in d.get("code_chunks", [])],
            doc_sections=[DocSection.from_dict(s) for s in d.get("doc_sections", [])],
            links=[Link.from_dict(l) for l in d.get("links", [])],
        )

    # -- convenience lookups -------------------------------------------------

    def chunk_by_id(self, chunk_id: str) -> Optional[CodeChunk]:
        return next((c for c in self.code_chunks if c.chunk_id == chunk_id), None)

    def section_by_id(self, section_id: str) -> Optional[DocSection]:
        return next((s for s in self.doc_sections if s.section_id == section_id), None)

    def sections_for_chunk(self, chunk_id: str) -> list[DocSection]:
        ids = {l.doc_section_id for l in self.links if l.code_chunk_id == chunk_id}
        return [s for s in self.doc_sections if s.section_id in ids]


@dataclass
class CodeChange:
    """A meaningful change to a code chunk detected from a git diff."""

    chunk_id: str
    file_path: str
    change_type: ChangeType
    old_source: Optional[str]
    new_source: Optional[str]
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["change_type"] = self.change_type.value
        return d


@dataclass
class StalenessFinding:
    """The verdict for a single suspect doc section."""

    doc_section_id: str
    chunk_id: str
    is_stale: bool
    confidence: Confidence
    diagnosis: str
    change_type: ChangeType = ChangeType.NONE

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["confidence"] = self.confidence.value
        d["change_type"] = self.change_type.value
        return d


class RepairAction(str, enum.Enum):
    """What the repair engine decided to do with a stale section."""

    AUTO_FIX = "auto_fix"
    DRAFT_FIX = "draft_fix"
    FLAG_ONLY = "flag_only"
    SKIP = "skip"


@dataclass
class Correction:
    """A generated (and possibly validated) doc correction."""

    doc_section_id: str
    action: RepairAction
    original_content: str
    corrected_content: Optional[str]
    confidence: Confidence
    diagnosis: str
    validation_passed: Optional[bool] = None
    validation_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["action"] = self.action.value
        d["confidence"] = self.confidence.value
        return d
