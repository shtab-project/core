FROM python:3.13-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY core/ ./core/
RUN uv sync --all-packages --no-dev

EXPOSE 8000
ENV UV_NO_DEV=1
CMD ["sh", "-c", "uv sync --all-packages && .venv/bin/alembic -c core/alembic.ini upgrade head && exec .venv/bin/uvicorn shtab_core.main:app --host 0.0.0.0 --port 8000"]
