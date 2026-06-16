# Full-stack dashboard image: builds the React app, then serves it (and the
# engine API) with FastAPI/uvicorn. Runs the engine in deterministic mock mode,
# so it needs no API key and is free to host. Build context = repo root.

# ── stage 1: build the dashboard ────────────────────────────────────────────
FROM node:20-slim AS web
WORKDIR /web
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ ./
RUN npm run build

# ── stage 2: python server ──────────────────────────────────────────────────
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DOCPILOT_LLM_PROVIDER=mock \
    DOCPILOT_EMBEDDING_PROVIDER=mock
WORKDIR /app

COPY pyproject.toml README.md requirements.txt ./
COPY docpilot ./docpilot
RUN pip install --upgrade pip && pip install ".[server]"

# Built dashboard -> served by FastAPI at "/"
COPY --from=web /web/dist ./dashboard/dist

# Hosts inject $PORT; default to 8000 locally.
ENV PORT=8000
CMD ["sh", "-c", "uvicorn docpilot.server.app:app --host 0.0.0.0 --port ${PORT}"]
