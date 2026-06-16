"""Link graph construction between code chunks and doc sections.

Two strategies are combined into one unified graph:

* **Heuristic (Phase A):** a doc section that mentions a code symbol (function,
  class, config key, CLI command, or API route) by name is linked to the
  matching chunk. Exact and precise -- high-precision signal.
* **Embedding (Phase B):** every chunk and section is embedded; pairs whose
  cosine similarity exceeds ``similarity_threshold`` are linked. Catches
  semantic relationships heuristics miss.

Heuristic links win when both strategies fire on the same pair.
"""

from __future__ import annotations

import logging
from typing import Optional

from .config import Config
from .embeddings import EmbeddingStore
from .models import ChunkKind, CodeChunk, DocSection, Link, LinkType

logger = logging.getLogger("docpilot.linker")


class Linker:
    """Builds the unified code<->docs link graph."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def build_links(
        self,
        chunks: list[CodeChunk],
        sections: list[DocSection],
        store: Optional[EmbeddingStore] = None,
    ) -> list[Link]:
        heuristic = self._heuristic_links(chunks, sections)
        embedding = self._embedding_links(chunks, sections, store)
        merged = self._merge(heuristic, embedding)
        logger.info(
            "Built %d links (%d heuristic, %d embedding-only)",
            len(merged),
            len(heuristic),
            len(merged) - len(heuristic),
        )
        return merged

    # -- Phase A: heuristic --------------------------------------------------

    def _heuristic_links(
        self, chunks: list[CodeChunk], sections: list[DocSection]
    ) -> list[Link]:
        # Build lookup tables from the various names a chunk can be cited by.
        by_name: dict[str, list[CodeChunk]] = {}

        def register(name: str, chunk: CodeChunk) -> None:
            if name:
                by_name.setdefault(name, []).append(chunk)

        for c in chunks:
            register(c.symbol, c)
            # bare method name (Class.method -> method)
            if "." in c.symbol:
                register(c.symbol.split(".")[-1], c)
            if c.kind is ChunkKind.CONFIG:
                register(c.metadata.get("config_key", ""), c)
                register(c.metadata.get("env_var", ""), c)
            if c.kind is ChunkKind.API_ROUTE:
                route = c.metadata.get("route")
                method = c.metadata.get("method", "")
                if route:
                    register(route, c)
                    register(f"{method} {route}".strip(), c)

        links: list[Link] = []
        seen: set[tuple[str, str]] = set()
        for section in sections:
            for ref in section.code_references:
                for chunk in by_name.get(ref, []):
                    key = (chunk.chunk_id, section.section_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    links.append(
                        Link(
                            code_chunk_id=chunk.chunk_id,
                            doc_section_id=section.section_id,
                            link_type=LinkType.HEURISTIC,
                            similarity_score=1.0,
                            evidence=ref,
                        )
                    )
        return links

    # -- Phase B: embedding --------------------------------------------------

    def _embedding_links(
        self,
        chunks: list[CodeChunk],
        sections: list[DocSection],
        store: Optional[EmbeddingStore],
    ) -> list[Link]:
        if store is None:
            store = EmbeddingStore(self.config)
            store.index_chunks(chunks)
            store.index_sections(sections)
        pairs = store.all_pairs_above(self.config.similarity_threshold)
        return [
            Link(
                code_chunk_id=cid,
                doc_section_id=sid,
                link_type=LinkType.EMBEDDING,
                similarity_score=round(score, 4),
            )
            for cid, sid, score in pairs
        ]

    # -- merge ---------------------------------------------------------------

    @staticmethod
    def _merge(heuristic: list[Link], embedding: list[Link]) -> list[Link]:
        merged: dict[tuple[str, str], Link] = {}
        for link in embedding:
            merged[(link.code_chunk_id, link.doc_section_id)] = link
        # Heuristic links overwrite embedding links for the same pair.
        for link in heuristic:
            merged[(link.code_chunk_id, link.doc_section_id)] = link
        return list(merged.values())
