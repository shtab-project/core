"""Login via Authentik (OIDC Authorization Code) and logout."""

from authlib.integrations.base_client import OAuthError
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import RedirectResponse

from shtab_core.config import settings
from shtab_core.constants import COOKIE, DEFAULT_NEXT
from shtab_core.dependencies import Auth
from shtab_core.exceptions import InvalidInputError
from shtab_core.oidc import Oidc
from shtab_core.schemas import LogoutOut
from shtab_core.services.auth import OidcClaims
from shtab_core.sessions import Sessions

router = APIRouter(prefix="/api/auth", tags=["auth"])


def safe_next(redirect_path: str | None) -> str:
    """Only a relative path inside Shtab: guards against open redirects."""
    if redirect_path and redirect_path.startswith("/"):
        if not redirect_path.startswith(("//", "/\\")):
            return redirect_path
    return DEFAULT_NEXT


@router.get("/login", summary="Start login (redirect to Authentik)")
async def login(request: Request, oidc: Oidc, next: str | None = None):
    """**Open it in the browser address bar**, not with the Execute button: it
    redirects to the Authentik login page, which Swagger can't show.

    `next` is the Shtab path to return to after login (e.g. `/api/docs`).
    """
    request.session["next"] = safe_next(next)
    return await oidc.authorize_redirect(
        request, f"{settings.public_url}/api/auth/callback"
    )


@router.get("/callback", summary="Return from Authentik", include_in_schema=False)
async def callback(request: Request, sessions: Sessions, oidc: Oidc, auth: Auth):
    try:
        token = await oidc.authorize_access_token(request)
    except OAuthError as oauth_error:
        raise InvalidInputError(f"Login failed: {oauth_error.error}") from None

    user = await auth.upsert_from_claims(
        OidcClaims.from_userinfo(token.get("userinfo") or {})
    )
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


@router.post("/logout", response_model=LogoutOut, summary="Log out")
async def logout(request: Request, response: Response, sessions: Sessions, oidc: Oidc):
    if session_id := request.cookies.get(COOKIE):
        await sessions.delete(session_id)
    response.delete_cookie(COOKIE, path="/")
    metadata = await oidc.load_server_metadata()
    return LogoutOut(logout_url=metadata.get("end_session_endpoint"))
