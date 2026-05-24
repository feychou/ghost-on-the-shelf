# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY core ./core
COPY rituals ./rituals
COPY signal_chamber ./signal_chamber
COPY main.py README.md ./

RUN set -eu; \
    if [ ! -s core/shelf/ghost_runtime.md ] || [ ! -s core/shelf/indexes/memory_index.json ]; then \
        echo "Missing generated shelf artifacts. Run the rituals locally before building the image." >&2; \
        exit 1; \
    fi

FROM python:3.12-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

RUN groupadd --system ghost && useradd --system --gid ghost ghost

COPY --from=builder --chown=ghost:ghost /app /app

USER ghost
EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn signal_chamber.server.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
