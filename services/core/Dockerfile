# Сборка из корня репозитория (uv-workspace):
#   docker build -f services/core/Dockerfile .
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Сначала только зависимости — слой кэшируется, пока не менялся uv.lock
COPY pyproject.toml uv.lock ./
COPY services/core/pyproject.toml services/core/
RUN uv sync --frozen --no-dev --package shtab-core --no-install-workspace

COPY services/core services/core
RUN uv sync --frozen --no-dev --package shtab-core

WORKDIR /app/services/core
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn shtab_core.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
