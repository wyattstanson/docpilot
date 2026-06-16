# DocPilot GitHub Action container.
# Build context is the repository root (where action.yml lives).
FROM python:3.11-slim

# git is needed for diff extraction and pushing fix branches.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/docpilot

# Install the package with the providers + GitHub extras.
COPY pyproject.toml README.md requirements.txt ./
COPY docpilot ./docpilot
RUN pip install --upgrade pip \
    && pip install ".[openai,anthropic,chroma,github]"

# GitHub mounts the repo at GITHUB_WORKSPACE and runs from there.
ENTRYPOINT ["python", "-m", "docpilot.action.entrypoint"]
