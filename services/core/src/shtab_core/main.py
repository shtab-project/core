from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from shtab_core.config import settings
from shtab_core.routers import auth, setup, users
from shtab_core.services.errors import (
    ConflictError,
    InvalidInputError,
    NotFoundError,
    ServiceError,
    UnauthorizedError,
)

app = FastAPI(
    title="Shtab Core",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)

# Короткоживущая подписанная cookie только для state/nonce на время входа через Authentik.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="shtab_oidc",
    max_age=600,
    same_site="lax",
    https_only=settings.secure_cookies,
)

app.include_router(auth.router)
app.include_router(setup.router)
app.include_router(users.router)


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    status_code = {
        InvalidInputError: status.HTTP_400_BAD_REQUEST,
        UnauthorizedError: status.HTTP_401_UNAUTHORIZED,
        NotFoundError: status.HTTP_404_NOT_FOUND,
        ConflictError: status.HTTP_409_CONFLICT,
    }.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


@app.get("/api/health", tags=["system"])
async def health():
    return {"status": "ok"}
