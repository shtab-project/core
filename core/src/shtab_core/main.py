from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from shtab_core.config import settings
from shtab_core.db import get_session_factory
from shtab_core.mcp_auth import router as mcp_tokens_router
from shtab_core.mcp_gateway import mount_mcp
from shtab_core.routers import auth, plugin_ui, plugins, setup, users
from shtab_core.services.errors import (
    ConflictError,
    InvalidInputError,
    NotFoundError,
    ServiceError,
    UnauthorizedError,
)
from shtab_core.services.plugins import PluginLoader
from shtab_core.uow import UnitOfWork


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    # Та же фабрика, что у HTTP-запросов; переопределение используется в тестах.
    factory_provider = application.dependency_overrides.get(
        get_session_factory, get_session_factory
    )
    loader = getattr(application.state, "plugin_loader", None)
    if loader is None:
        loader = PluginLoader(application)
        application.state.plugin_loader = loader
    async with UnitOfWork(factory_provider()) as uow:
        for plugin in await uow.plugins.list_all():
            loader.restore(plugin)
    async with application.state.mcp.session_manager.run():
        yield


async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    codes_status: dict[type[Exception], int] = {
        InvalidInputError: status.HTTP_400_BAD_REQUEST,
        UnauthorizedError: status.HTTP_401_UNAUTHORIZED,
        NotFoundError: status.HTTP_404_NOT_FOUND,
        ConflictError: status.HTTP_409_CONFLICT,
    }

    status_code: int = codes_status.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


async def health():
    return {"status": "ok"}


def create_app() -> FastAPI:
    application = FastAPI(
        title="Shtab Core",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )
    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="shtab_oidc",
        max_age=600,
        same_site="lax",
        https_only=settings.secure_cookies,
    )
    application.include_router(auth.router)
    application.include_router(setup.router)
    application.include_router(users.router)
    application.include_router(mcp_tokens_router)
    application.include_router(plugins.router)
    application.include_router(plugin_ui.router)
    application.add_exception_handler(ServiceError, service_error_handler)
    application.add_api_route("/api/health", health, methods=["GET"], tags=["system"])
    mount_mcp(application)
    return application


app = create_app()
