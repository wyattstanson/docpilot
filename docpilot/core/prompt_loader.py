"""Loader for the versioned prompt templates in ``docpilot/prompts``.

Templates use a ``SYSTEM:`` / ``USER:`` split and ``{placeholder}`` variables.
Substitution is done with a safe replacer that only touches known placeholders,
so the literal ``{`` / ``}`` braces in the embedded JSON examples are preserved.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


@lru_cache(maxsize=None)
def _read(name: str) -> str:
    path = _PROMPT_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")


def _split(template: str) -> tuple[str, str]:
    """Split a template into (system, user) on the ``SYSTEM:``/``USER:`` markers."""
    sys_match = re.search(r"^SYSTEM:\s*$", template, re.MULTILINE)
    usr_match = re.search(r"^USER:\s*$", template, re.MULTILINE)
    if not sys_match or not usr_match:
        # No markers -> whole thing is the user prompt.
        return "", template
    system = template[sys_match.end() : usr_match.start()].strip()
    user = template[usr_match.end() :].strip()
    return system, user


def _fill(text: str, values: dict[str, str]) -> str:
    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key in values:
            return str(values[key])
        return m.group(0)  # leave unknown braces (JSON examples) untouched

    return _PLACEHOLDER.sub(repl, text)


def render(name: str, **values: object) -> tuple[str, str]:
    """Return ``(system_prompt, user_prompt)`` for template ``name``."""
    system, user = _split(_read(name))
    str_values = {k: ("" if v is None else str(v)) for k, v in values.items()}
    return _fill(system, str_values), _fill(user, str_values)
