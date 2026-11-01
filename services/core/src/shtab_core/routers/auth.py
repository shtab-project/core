"""Вход через Authentik (OIDC Authorization Code) и выход."""

from authlib.integrations.base_client import OAuthError
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from shtab_core.config import settings
from shtab_core.constants import COOKIE, DEFAULT_NEXT
from shtab_core.dependencies import Auth
from shtab_core.oidc import Oidc
from shtab_core.schemas import LogoutOut
from shtab_core.sessions import Sessions

router = APIRouter(prefix="/api/auth", tags=["auth"])


def safe_next(value: str | None) -> str:
    """Только относительный путь внутри Shtab — защита от открытого редиректа."""
    if value and value.startswith("/") and not value.startswith(("//", "/\\")):
        return value
    return DEFAULT_NEXT


@router.get("/login", summary="Начать вход (редирект в Authentik)")
async def login(request: Request, oidc: Oidc, next: str | None = None):
    """**Открывать в адресной строке браузера**, а не кнопкой Execute: это переход
    на страницу входа Authentik, Swagger его не покажет.

    `next` — путь в Shtab, куда вернуться после входа (например `/api/docs`), не логин.
    """
    request.session["next"] = safe_next(next)
    return await oidc.authorize_redirect(request, f"{settings.public_url}/api/auth/callback")


@router.get("/callback", summary="Возврат из Authentik", include_in_schema=False)
async def callback(request: Request, sessions: Sessions, oidc: Oidc, auth: Auth):
    try:
        token = await oidc.authorize_access_token(request)
    except OAuthError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Вход не удался: {e.error}") from None

    user = await auth.upsert_from_claims(token.get("userinfo") or {})
    session_id = await sessions.create(user.id)

    response = RedirectResponse(
        request.session.pop("next", DEFAULT_NEXT), status.HTTP_303_SEE_OTHER
    )
    response.set_cookie(
        COOKIE,
        session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
        path="/",
    )
    return response


@router.post("/logout", response_model=LogoutOut, summary="Выйти")
async def logout(request: Request, response: Response, sessions: Sessions, oidc: Oidc):
    if session_id := request.cookies.get(COOKIE):
        await sessions.delete(session_id)
    response.delete_cookie(COOKIE, path="/")
    metadata = await oidc.load_server_metadata()
    return LogoutOut(logout_url=metadata.get("end_session_endpoint"))
