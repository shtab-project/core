"""MCP tokens: issued per user, kept in Redis as hashes, checked on every request."""

import hashlib
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError
from redis.asyncio import Redis

from shtab_core.sessions import redis

TOKEN_TTL = timedelta(days=30)


def datetime_now() -> datetime:
    return datetime.now(UTC)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


@dataclass
class MCPToken:
    """An MCP token value with its lifetime."""

    value: str = field(default_factory=generate_token)
    created_at: datetime = field(default_factory=datetime_now)
    ttl: timedelta = TOKEN_TTL

    @property
    def expires_at(self) -> datetime:
        return self.created_at + self.ttl

    def __bool__(self) -> bool:
        """`if token:` means the token is still alive."""
        return self.expires_at > datetime_now()

    def __eq__(self, value: object) -> bool:
        """`token == incoming`: constant-time and expiry-aware."""
        if isinstance(value, str):
            return bool(self) and secrets.compare_digest(self.value, value)

        return NotImplemented

    # `token == "..."` can be True, so hash(token) would have to equal
    # hash("..."), which leaks the secret. A mutable secret stays unhashable.
    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        """Never print the secret: show a short prefix and the state."""
        state = "alive" if self else "expired"
        until = f"{self.expires_at:%Y-%m-%d %H:%M:%S %Z}"
        return f"<MCPToken {self.value[:4]}… {state} until {until}>"


@dataclass(frozen=True)
class McpTokenInfo:
    id: str
    expires_in: int


@dataclass
class McpStorage:
    """Issues per-user MCP tokens, lists and revokes them.

    Redis is the source of truth: shared by all workers, survives restarts and
    drops expired tokens by itself via the key TTL.

    Layout:
        mcp-token:<token id>      -> user id          (TTL = token lifetime)
        user-mcp-tokens:<user id> -> set of token keys (to list and revoke them)
    """

    client: Redis
    ttl: timedelta = TOKEN_TTL
    prefix: str = "mcp-token:"

    @staticmethod
    def token_id(value: str) -> str:
        # Only the hash is stored, so a Redis dump hands out no live tokens.
        # Lookup by hash also makes `compare_digest` unnecessary.
        return hashlib.sha256(value.encode()).hexdigest()

    def _key(self, token_id: str) -> str:
        return self.prefix + token_id

    @staticmethod
    def _owned(user_id: UUID) -> str:
        return f"user-mcp-tokens:{user_id}"

    async def __call__(self, user_id: UUID) -> MCPToken:
        """`await storage(user_id)` issues a fresh token for that user."""
        token = MCPToken(ttl=self.ttl)
        key, owned = self._key(self.token_id(token.value)), self._owned(user_id)

        async with self.client.pipeline(transaction=True) as pipe:
            pipe.set(key, str(user_id), ex=self.ttl)
            pipe.sadd(owned, key)
            pipe.expire(owned, self.ttl)
            await pipe.execute()

        return token

    async def owner(self, value: str) -> UUID | None:
        """Who owns this token, or None if it was never issued or has expired."""
        return await self._owner_of(self._key(self.token_id(value)))

    async def _owner_of(self, key: str) -> UUID | None:
        user_id: str | bytes | None = await self.client.get(key)
        if not user_id:
            return None
        return UUID(user_id.decode() if isinstance(user_id, bytes) else user_id)

    async def list_for(self, user_id: UUID) -> list[McpTokenInfo]:
        """The user's live tokens, longest-lived first; drops expired leftovers."""
        owned = self._owned(user_id)
        tokens, stale = [], []
        for raw in await self.client.smembers(owned):  # type: ignore[misc]
            key = raw.decode() if isinstance(raw, bytes) else raw
            expires_in = await self.client.ttl(key)
            if expires_in > 0:
                token_id = key.removeprefix(self.prefix)
                tokens.append(McpTokenInfo(id=token_id, expires_in=expires_in))
            else:
                stale.append(key)
        if stale:
            await self.client.srem(owned, *stale)  # type: ignore[misc]
        return sorted(tokens, key=lambda token: token.expires_in, reverse=True)

    async def revoke(self, user_id: UUID, token_id: str) -> bool:
        """Kill one of the user's tokens; False if the user has no such token."""
        key = self._key(token_id)
        if await self._owner_of(key) != user_id:
            return False

        async with self.client.pipeline(transaction=True) as pipe:
            pipe.delete(key)
            pipe.srem(self._owned(user_id), key)
            await pipe.execute()

        return True

    async def revoke_user(self, user_id: UUID) -> None:
        """Kill every token of a user, e.g. after the account is disabled."""
        owned = self._owned(user_id)
        keys = await self.client.smembers(owned)  # type: ignore[misc]
        await self.client.delete(owned, *keys)


class TokenOwners(Protocol):
    """All that `MCPAuth` needs from a token store: who owns a token."""

    async def owner(self, value: str) -> UUID | None: ...


@dataclass
class MCPAuth:
    """Turns a bearer token into the caller's identity.

    Implements the MCP SDK `TokenVerifier` protocol. The SDK does the HTTP part
    on every request: reads `Authorization: Bearer ...` and answers 401 with
    `WWW-Authenticate` when this returns None.
    """

    storage: TokenOwners
    is_active: Callable[[UUID], Awaitable[bool]]
    client_id: str = "shtab-mcp"

    async def verify_token(self, token: str) -> AccessToken | None:
        user_id = await self.storage.owner(token)
        if not user_id or not await self.is_active(user_id):
            return None
        return AccessToken(
            token=token,
            client_id=self.client_id,
            subject=str(user_id),
            scopes=[],
        )


def require_mcp_user_id() -> UUID:
    """The id of the user calling an MCP tool."""
    access = get_access_token()
    if not access or not access.subject:
        raise ToolError("A Shtab token is required")
    return UUID(access.subject)


def get_mcp_tokens() -> McpStorage:
    return McpStorage(redis)


McpTokens = Annotated[McpStorage, Depends(get_mcp_tokens)]
