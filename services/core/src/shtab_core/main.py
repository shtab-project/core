from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from shtab_core.config import settings
from shtab_core.routers import auth, setup, users

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


@app.get("/api/health", tags=["system"])
async def health():
    return {"status": "ok"}
