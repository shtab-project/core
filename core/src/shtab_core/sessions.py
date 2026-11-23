"""Browser sessions: an opaque id in the cookie, data in Redis.

Redis keeps only the id hash, so a Redis leak yields no usable cookies.
Deleting the key revokes the session.
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from shtab_core.config import settings

redis = Redis.from_url(settings.redis_url, decode_responses=True)  # type: ignore


def _key(session_id: str) -> str:
    return "session:" + hashlib.sha256(session_id.encode()).hexdigest()


def _user_key(user_id: uuid.UUID) -> str:
    """Set of the user's session keys, to revoke them all at once."""
    return f"user-sessions:{user_id}"


@dataclass
class SessionStore:
    client: Redis
    ttl: int

    async def create(self, user_id: uuid.UUID) -> str:
        session_id = secrets.token_urlsafe(32)
        session_key = _key(session_id)

        async with self.client.pipeline(transaction=True) as pipe:
            pipe.set(session_key, str(user_id), ex=self.ttl)
            pipe.sadd(_user_key(user_id), session_key)
            pipe.expire(_user_key(user_id), self.ttl)
            await pipe.execute()

        return session_id

    async def get(self, session_id: str) -> uuid.UUID | None:
        stored_user_id = await self.client.get(_key(session_id))
        return uuid.UUID(stored_user_id) if stored_user_id else None  # type:ignore[reportArgumentType]

    async def delete(self, session_id: str) -> None:
        await self.client.delete(_key(session_id))

    async def revoke_user(self, user_id: uuid.UUID) -> None:
        """End all of the user's sessions (e.g. after the account is disabled)."""
        user_key = _user_key(user_id)
        session_keys = await self.client.smembers(user_key)  # type: ignore[misc]
        await self.client.delete(user_key, *session_keys)


def get_sessions() -> SessionStore:
    return SessionStore(redis, settings.session_ttl_seconds)


Sessions = Annotated[SessionStore, Depends(get_sessions)]
