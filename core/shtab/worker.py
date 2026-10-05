"""Фоновые задачи (taskiq + Redis).

Запуск воркера: taskiq worker shtab.worker:broker
"""

from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from shtab.config import settings
from shtab.db import SessionLocal
from shtab.models import Scope
from shtab.notes.indexer import reindex_space
from shtab.tasks import get_or_create_user

broker = ListQueueBroker(settings.redis_url).with_result_backend(
    RedisAsyncResultBackend(settings.redis_url, result_ex_time=3600)
)


@broker.task
async def reindex(scope: str, username: str | None = None) -> int:
    async with SessionLocal() as session:
        owner = await get_or_create_user(session, username) if username else None
        return await reindex_space(session, Scope(scope), owner)


@broker.task
async def reindex_all() -> int:
    total = await reindex(Scope.shared)
    users_dir = settings.notes_root / "users"
    if users_dir.is_dir():
        for user_dir in sorted(p for p in users_dir.iterdir() if p.is_dir()):
            total += await reindex(Scope.personal, user_dir.name)
    return total
