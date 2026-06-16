"""Core engine for DocPilot.

Modules:
    models            -- shared dataclasses (code chunks, doc sections, links).
    config            -- configuration management.
    llm               -- provider-agnostic LLM + embedding abstraction.
    parser            -- code and documentation parsing.
    embeddings        -- embedding generation and vector storage.
    linker            -- code-to-docs link graph construction.
    diff_analyzer     -- git diff parsing and meaningful-change detection.
    staleness_checker -- LLM-based staleness verification.
    repair_engine     -- doc correction generation and validation.
    pipeline          -- end-to-end orchestration.
"""
