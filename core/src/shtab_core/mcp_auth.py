from collections.abc import Callable
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Response
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shtab_core.dependencies import CurrentUser
from shtab_core.sessions import redis
from shtab_core.uow import UnitOfWork

router = APIRouter(prefix="/api/me/mcp-tokens", tags=["mcp"])
TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60


def token_key(token_id: UUID) -> str:
    return f"mcp-token:{token_id}"


def digest(token: str) -> str:
    return sha256(token.encode()).hexdigest()


class ShtabTokenVerifier:
    def __init__(self, factory_provider: Callable[[], async_sessionmaker[AsyncSession]]) -> None:
        self.factory_provider = factory_provider

    async def verify_token(self, token: str) -> AccessToken | None:
        token_id, separator, secret = token.partition(".")
        if not separator or len(secret) != 43:
            return None
        try:
            key = token_key(UUID(token_id))
        except ValueError:
            return None
        entry = await redis.get(key)
        if not entry:
            return None
        user_id, stored_digest = entry.split(":")
        if not compare_digest(stored_digest, digest(token)):
            return None
        async with UnitOfWork(self.factory_provider()) as uow:
            if await uow.users.get(UUID(user_id)) is None:
                return None
        return AccessToken(token=token, client_id=token_id, subject=user_id, scopes=[])


def require_mcp_user_id() -> UUID:
    access = get_access_token()
    if access is None or access.subject is None:
        raise ToolError("Нужен токен Shtab")
    return UUID(access.subject)


@router.post("", status_code=201)
async def issue_token(user: CurrentUser, response: Response) -> dict[str, str | int]:
    token_id = uuid4()
    token = f"{token_id}.{token_urlsafe(32)}"
    await redis.set(token_key(token_id), f"{user.id}:{digest(token)}", ex=TOKEN_TTL_SECONDS)
    response.headers["Cache-Control"] = "no-store"
    return {"id": str(token_id), "token": token, "expires_in": TOKEN_TTL_SECONDS}


@router.delete("/{token_id}", status_code=204)
async def revoke_token(token_id: UUID, user: CurrentUser) -> Response:
    key = token_key(token_id)
    entry = await redis.get(key)
    if not entry or entry.split(":", 1)[0] != str(user.id):
        raise HTTPException(404, "Токен не найден")
    await redis.delete(key)
    return Response(status_code=204)
