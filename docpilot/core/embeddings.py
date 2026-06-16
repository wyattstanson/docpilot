"""Embedding generation and vector storage.

This module computes embeddings for code chunks and doc sections and persists
them. ChromaDB is used when available (file-based, zero-server); otherwise an
in-memory store is used so the engine still runs. Either way the public API is
identical.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .config import Config
from .llm import EmbeddingClient, cosine_similarity, get_embedding_client
from .models import CodeChunk, DocSection

logger = logging.getLogger("docpilot.embeddings")


def chunk_embedding_text(chunk: CodeChunk) -> str:
    """The text representation of a code chunk used for embedding."""
    parts = [chunk.symbol, chunk.signature or "", chunk.docstring or "", chunk.source]
    return "\n".join(p for p in parts if p)[:6000]


def section_embedding_text(section: DocSection) -> str:
    return f"{section.heading_path}\n{section.content}"[:6000]


class EmbeddingStore:
    """Stores and queries embeddings for chunks and sections."""

    def __init__(self, config: Config, client: Optional[EmbeddingClient] = None) -> None:
        self.config = config
        self.client = client or get_embedding_client(config)
        self._chunk_vecs: dict[str, list[float]] = {}
        self._section_vecs: dict[str, list[float]] = {}
        self._chroma = _maybe_open_chroma(config)

    # -- indexing ------------------------------------------------------------

    def index_chunks(self, chunks: list[CodeChunk]) -> None:
        if not chunks:
            return
        texts = [chunk_embedding_text(c) for c in chunks]
        vecs = self.client.embed(texts)
        for c, v in zip(chunks, vecs):
            self._chunk_vecs[c.chunk_id] = v
        self._persist("code_chunks", [c.chunk_id for c in chunks], vecs, texts)
        logger.info("Indexed %d code chunk embeddings", len(chunks))

    def index_sections(self, sections: list[DocSection]) -> None:
        if not sections:
            return
        texts = [section_embedding_text(s) for s in sections]
        vecs = self.client.embed(texts)
        for s, v in zip(sections, vecs):
            self._section_vecs[s.section_id] = v
        self._persist("doc_sections", [s.section_id for s in sections], vecs, texts)
        logger.info("Indexed %d doc section embeddings", len(sections))

    # -- querying ------------------------------------------------------------

    def chunk_vector(self, chunk_id: str) -> Optional[list[float]]:
        return self._chunk_vecs.get(chunk_id)

    def section_vector(self, section_id: str) -> Optional[list[float]]:
        return self._section_vecs.get(section_id)

    def similar_sections(
        self, chunk_id: str, threshold: float
    ) -> list[tuple[str, float]]:
        """Return (section_id, score) pairs above ``threshold`` for a chunk."""
        cv = self._chunk_vecs.get(chunk_id)
        if cv is None:
            return []
        out = []
        for sid, sv in self._section_vecs.items():
            score = cosine_similarity(cv, sv)
            if score >= threshold:
                out.append((sid, score))
        return sorted(out, key=lambda x: x[1], reverse=True)

    def all_pairs_above(
        self, threshold: float
    ) -> list[tuple[str, str, float]]:
        """All (chunk_id, section_id, score) pairs scoring >= threshold."""
        pairs: list[tuple[str, str, float]] = []
        for cid, cv in self._chunk_vecs.items():
            for sid, sv in self._section_vecs.items():
                score = cosine_similarity(cv, sv)
                if score >= threshold:
                    pairs.append((cid, sid, score))
        return pairs

    # -- persistence ---------------------------------------------------------

    def _persist(
        self, collection: str, ids: list[str], vecs: list[list[float]], docs: list[str]
    ) -> None:
        if self._chroma is None:
            return
        try:
            col = self._chroma.get_or_create_collection(collection)
            col.upsert(ids=ids, embeddings=vecs, documents=docs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ChromaDB persist failed for %s: %s", collection, exc)


def _maybe_open_chroma(config: Config):
    """Open a persistent ChromaDB client, or return None if unavailable."""
    try:
        import chromadb  # lazy import
    except ImportError:
        logger.info("chromadb not installed; using in-memory embedding store.")
        return None
    try:
        path = Path(config.repo_root) / config.chroma_dir
        path.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(path))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not open ChromaDB at %s: %s", config.chroma_dir, exc)
        return None
