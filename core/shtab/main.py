from contextlib import asynccontextmanager

from fastapi import FastAPI

from shtab.api import tasks
from shtab.mcp_server import build_app, mcp
from shtab.worker import broker

mcp_app = build_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Вложенное Starlette-приложение MCP свой lifespan не получит — запускаем вручную.
    async with mcp.session_manager.run():
        if not broker.is_worker_process:
            await broker.startup()
        yield
        if not broker.is_worker_process:
            await broker.shutdown()


app = FastAPI(title="Shtab", version="0.1.0", lifespan=lifespan)
app.include_router(tasks.router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}


# Последним: всё, что не совпало с маршрутами выше, уходит в MCP (эндпоинт /mcp).
app.mount("/", mcp_app)
