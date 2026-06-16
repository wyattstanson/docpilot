"""Configuration management for DocPilot.

Settings are resolved with the following precedence (highest first):

1. Explicit keyword arguments to :meth:`Config.load`.
2. Environment variables (``DOCPILOT_*``, plus ``OPENAI_API_KEY`` /
   ``ANTHROPIC_API_KEY``).
3. A ``.docpilot/config.json`` file in the repository root.
4. Built-in defaults.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("docpilot.config")

_DEFAULT_DOC_PATHS = ["docs", "README.md"]
_DEFAULT_CODE_PATHS = ["src", "lib"]
_DEFAULT_EXCLUDES = ["node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build"]


def _split_csv(value: str) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()]


def _load_dotenv(repo_root: str) -> None:
    """Load ``KEY=VALUE`` pairs from a repo-root ``.env`` into ``os.environ``.

    Dependency-free. A real shell/CI environment variable always wins over the
    file (existing keys are never overwritten). Never raises.
    """
    path = Path(repo_root) / ".env"
    if not path.exists():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError as exc:
        logger.warning("Could not read .env: %s", exc)


@dataclass
class Config:
    """Resolved DocPilot configuration."""

    # -- providers -----------------------------------------------------------
    llm_provider: str = "openai"          # "openai" | "anthropic" | "mock"
    embedding_provider: str = "openai"    # "openai" | "mock"
    llm_model: str = ""                   # resolved per-provider if empty
    embedding_model: str = "text-embedding-3-small"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    # Point the OpenAI client at any OpenAI-compatible endpoint (Groq, Gemini,
    # OpenRouter, Ollama, ...). Leave empty for OpenAI itself.
    openai_base_url: Optional[str] = None

    # -- linking & detection -------------------------------------------------
    similarity_threshold: float = 0.78
    confidence_threshold: float = 0.75
    auto_merge: bool = False

    # -- paths ---------------------------------------------------------------
    repo_root: str = "."
    doc_paths: list[str] = field(default_factory=lambda: list(_DEFAULT_DOC_PATHS))
    code_paths: list[str] = field(default_factory=lambda: list(_DEFAULT_CODE_PATHS))
    exclude_dirs: list[str] = field(default_factory=lambda: list(_DEFAULT_EXCLUDES))

    # -- storage -------------------------------------------------------------
    docpilot_dir: str = ".docpilot"
    chroma_dir: str = ".docpilot/chroma"

    def resolved_llm_model(self) -> str:
        if self.llm_model:
            return self.llm_model
        return {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-6",
            "mock": "mock-llm",
        }.get(self.llm_provider, "gpt-4o")

    @property
    def mapping_path(self) -> Path:
        return Path(self.repo_root) / self.docpilot_dir / "mapping.json"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Never serialize secrets back to disk.
        d.pop("openai_api_key", None)
        d.pop("anthropic_api_key", None)
        return d

    # -- loading -------------------------------------------------------------

    @classmethod
    def load(cls, repo_root: str = ".", **overrides: Any) -> "Config":
        """Build a Config from file < env < explicit overrides."""
        cfg = cls(repo_root=repo_root)
        _load_dotenv(repo_root)
        cfg._apply_file(Path(repo_root) / ".docpilot" / "config.json")
        cfg._apply_env()
        for key, value in overrides.items():
            if value is not None and hasattr(cfg, key):
                setattr(cfg, key, value)
        cfg._validate()
        return cfg

    def _apply_file(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read config file %s: %s", path, exc)
            return
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def _apply_env(self) -> None:
        env = os.environ
        mapping = {
            "DOCPILOT_LLM_PROVIDER": "llm_provider",
            "DOCPILOT_EMBEDDING_PROVIDER": "embedding_provider",
            "DOCPILOT_LLM_MODEL": "llm_model",
            "DOCPILOT_EMBEDDING_MODEL": "embedding_model",
        }
        for env_key, attr in mapping.items():
            if env.get(env_key):
                setattr(self, attr, env[env_key])

        if env.get("DOCPILOT_SIMILARITY_THRESHOLD"):
            self.similarity_threshold = float(env["DOCPILOT_SIMILARITY_THRESHOLD"])
        if env.get("DOCPILOT_CONFIDENCE_THRESHOLD"):
            self.confidence_threshold = float(env["DOCPILOT_CONFIDENCE_THRESHOLD"])
        if env.get("DOCPILOT_AUTO_MERGE"):
            self.auto_merge = env["DOCPILOT_AUTO_MERGE"].lower() in {"1", "true", "yes"}
        if env.get("DOCPILOT_DOCS_PATHS"):
            self.doc_paths = _split_csv(env["DOCPILOT_DOCS_PATHS"])
        if env.get("DOCPILOT_CODE_PATHS"):
            self.code_paths = _split_csv(env["DOCPILOT_CODE_PATHS"])

        self.openai_api_key = env.get("OPENAI_API_KEY", self.openai_api_key)
        self.anthropic_api_key = env.get("ANTHROPIC_API_KEY", self.anthropic_api_key)
        self.openai_base_url = env.get("OPENAI_BASE_URL", self.openai_base_url)

    def _validate(self) -> None:
        # Fall back to the mock provider when a real key is unavailable so the
        # engine never crashes in offline / CI-without-secrets environments.
        if self.llm_provider == "openai" and not self.openai_api_key:
            logger.warning("No OPENAI_API_KEY found; LLM falling back to 'mock'.")
            self.llm_provider = "mock"
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            logger.warning("No ANTHROPIC_API_KEY found; LLM falling back to 'mock'.")
            self.llm_provider = "mock"
        if self.embedding_provider == "openai" and not self.openai_api_key:
            logger.warning("No OPENAI_API_KEY found; embeddings falling back to 'mock'.")
            self.embedding_provider = "mock"
        if not 0.0 <= self.similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be in [0, 1]")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be in [0, 1]")
