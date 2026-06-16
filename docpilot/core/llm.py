"""Provider-agnostic LLM and embedding clients.

DocPilot never imports a vendor SDK at module load time. Real providers
(``openai``, ``anthropic``) are imported lazily so the package installs and
runs with zero heavy dependencies. When no API key is configured, the engine
transparently falls back to deterministic *mock* clients so the full pipeline
remains runnable offline and in tests.

Two abstractions are exposed:

* :class:`EmbeddingClient` -- ``embed(texts) -> list[list[float]]``
* :class:`LLMClient`       -- ``chat_text`` / ``chat_json`` for completions

Use :func:`get_embedding_client` and :func:`get_llm_client` to construct the
right implementation for a :class:`~docpilot.core.config.Config`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from .config import Config

logger = logging.getLogger("docpilot.llm")

_EMBED_DIM = 256  # dimensionality of the deterministic mock embedding space.


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

class EmbeddingClient(ABC):
    """Turn text into vectors."""

    is_mock: bool = False

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input string."""

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class MockEmbeddingClient(EmbeddingClient):
    """Deterministic bag-of-words hashing embeddings.

    Produces L2-normalized vectors where texts sharing vocabulary land close
    together under cosine similarity. This is intentionally simple but yields
    *real* similarity structure, so linking behaves sensibly offline.
    """

    is_mock = True

    def __init__(self, dim: int = _EMBED_DIM) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]+", text.lower()):
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec
        return [v / norm for v in vec]


class OpenAIEmbeddingClient(EmbeddingClient):
    """OpenAI ``text-embedding-3-small`` (or configured) embeddings."""

    def __init__(
        self, api_key: str, model: str, batch_size: int = 128, base_url: Optional[str] = None
    ) -> None:
        self.model = model
        self.batch_size = batch_size
        try:
            from openai import OpenAI  # lazy import
        except ImportError as exc:  # pragma: no cover - exercised only w/ SDK
            raise RuntimeError(
                "openai package is required for the OpenAI embedding provider"
            ) from exc
        self._client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        # Batch to respect rate limits and reduce round-trips.
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            resp = _with_retry(
                lambda: self._client.embeddings.create(model=self.model, input=batch)
            )
            out.extend(item.embedding for item in resp.data)
        return out


def get_embedding_client(config: Config) -> EmbeddingClient:
    if config.embedding_provider == "openai" and config.openai_api_key:
        return OpenAIEmbeddingClient(
            config.openai_api_key, config.embedding_model, base_url=config.openai_base_url
        )
    if config.embedding_provider == "openai":
        logger.warning("OpenAI embeddings requested without key; using mock.")
    return MockEmbeddingClient()


# ---------------------------------------------------------------------------
# Chat completions
# ---------------------------------------------------------------------------

class LLMClient(ABC):
    """Chat-style completion client."""

    is_mock: bool = False

    @abstractmethod
    def chat_text(self, system: str, user: str) -> str:
        """Return a raw text completion."""

    def chat_json(self, system: str, user: str) -> dict[str, Any]:
        """Return a completion parsed as JSON.

        Robust to models that wrap JSON in prose or code fences.
        """
        raw = self.chat_text(system + "\n\nRespond with valid JSON only.", user)
        return _extract_json(raw)


class MockLLMClient(LLMClient):
    """A no-network LLM stand-in.

    It is never asked to free-form reason: the staleness checker and repair
    engine detect ``is_mock`` and run deterministic heuristics instead. This
    class exists so code paths that *do* call it degrade gracefully.
    """

    is_mock = True

    def chat_text(self, system: str, user: str) -> str:
        return json.dumps(
            {
                "note": "mock-llm: heuristic path should be used for analysis",
            }
        )


class OpenAILLMClient(LLMClient):
    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None) -> None:
        self.model = model
        try:
            from openai import OpenAI  # lazy import
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("openai package is required for the OpenAI provider") from exc
        self._client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    def chat_text(self, system: str, user: str) -> str:
        resp = _with_retry(
            lambda: self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
            )
        )
        return resp.choices[0].message.content or ""


class AnthropicLLMClient(LLMClient):
    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        try:
            import anthropic  # lazy import
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "anthropic package is required for the Anthropic provider"
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key)

    def chat_text(self, system: str, user: str) -> str:
        resp = _with_retry(
            lambda: self._client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.0,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        )
        parts = [block.text for block in resp.content if getattr(block, "type", "") == "text"]
        return "".join(parts)


def get_llm_client(config: Config) -> LLMClient:
    provider = config.llm_provider
    model = config.resolved_llm_model()
    if provider == "openai" and config.openai_api_key:
        return OpenAILLMClient(config.openai_api_key, model, base_url=config.openai_base_url)
    if provider == "anthropic" and config.anthropic_api_key:
        return AnthropicLLMClient(config.anthropic_api_key, model)
    if provider in {"openai", "anthropic"}:
        logger.warning("LLM provider %s requested without key; using mock.", provider)
    return MockLLMClient()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _with_retry(fn, attempts: int = 4, base_delay: float = 1.0):
    """Call ``fn`` with exponential backoff on transient errors."""
    last_exc: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - provider SDKs raise broadly
            last_exc = exc
            wait = base_delay * (2 ** attempt)
            logger.warning("LLM/embedding call failed (attempt %d): %s", attempt + 1, exc)
            if attempt < attempts - 1:
                time.sleep(wait)
    assert last_exc is not None
    raise last_exc


def _extract_json(raw: str) -> dict[str, Any]:
    """Pull the first JSON object out of a possibly-noisy completion."""
    raw = raw.strip()
    # Strip ```json ... ``` fences if present.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Fall back to the first balanced { ... } block.
    start = raw.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[start : i + 1])
                    except json.JSONDecodeError:
                        break
    logger.error("Could not parse JSON from completion: %.200s", raw)
    return {}


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
