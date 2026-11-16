"""Сессии браузера: непрозрачный id в cookie, данные — в Redis.

В Redis лежит только хэш id — утечка содержимого Redis не даёт готовых cookie.
Сессию можно отозвать, просто удалив ключ.
"""

import hashlib
import secrets
import uuid
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from shtab_core.config import settings

redis = Redis.from_url(settings.redis_url, decode_responses=True)


def _key(session_id: str) -> str:
    return "session:" + hashlib.sha256(session_id.encode()).hexdigest()


class SessionStore:
    def __init__(self, client: Redis, ttl: int) -> None:
        self.client = client
        self.ttl = ttl

    async def create(self, user_id: uuid.UUID) -> str:
        session_id = secrets.token_urlsafe(32)
        session_key = _key(session_id)
        await self.client.set(session_key, str(user_id), ex=self.ttl)
        return session_id

    async def get(self, session_id: str) -> uuid.UUID | None:
        stored_user_id = await self.client.get(_key(session_id))
        return uuid.UUID(stored_user_id) if stored_user_id else None  # type:ignore[reportArgumentType]

    async def delete(self, session_id: str) -> None:
        await self.client.delete(_key(session_id))


def get_sessions() -> SessionStore:
    return SessionStore(redis, settings.session_ttl_seconds)


Sessions = Annotated[SessionStore, Depends(get_sessions)]
