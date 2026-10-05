"""Сервис задач целиком: файлы ↔ индекс, права личное/общее. БД — SQLite в памяти."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shtab import tasks
from shtab.config import settings
from shtab.db import Base
from shtab.models import Scope, Status
from shtab.notes.indexer import reindex_space


@pytest.fixture
async def session(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "notes_root", tmp_path)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def test_personal_and_shared_visibility(session, tmp_path):
    alice = await tasks.get_or_create_user(session, "alice")
    bob = await tasks.get_or_create_user(session, "bob")

    await tasks.create_task(session, alice, "Личное Алисы")
    await tasks.create_task(session, bob, "Общая задача", scope=Scope.shared)

    assert {t.title for t in await tasks.list_tasks(session, alice)} == {
        "Личное Алисы",
        "Общая задача",
    }
    assert {t.title for t in await tasks.list_tasks(session, bob)} == {"Общая задача"}
    assert (
        (tmp_path / "users" / "alice" / "Inbox.md")
        .read_text("utf-8")
        .endswith("- [ ] Личное Алисы\n")
    )


async def test_move_writes_markdown_and_keeps_id(session, tmp_path):
    alice = await tasks.get_or_create_user(session, "alice")
    task = await tasks.create_task(session, alice, "Сделать отчёт", tags=["отчёты"])

    moved = await tasks.move_task(session, alice, task.id, Status.doing)
    assert moved.id == task.id and moved.status is Status.doing
    inbox = tmp_path / "users" / "alice" / "Inbox.md"
    assert "- [ ] Сделать отчёт #отчёты [status: doing]" in inbox.read_text("utf-8")

    # Правка файла «руками» (как из SilverBullet) выше задачи — id не меняется.
    inbox.write_text("Заметка сверху\n" + inbox.read_text("utf-8"), "utf-8")
    await reindex_space(session, Scope.personal, alice)
    done = await tasks.move_task(session, alice, task.id, Status.done)
    assert done.id == task.id and done.done


async def test_cannot_move_foreign_personal_task(session):
    alice = await tasks.get_or_create_user(session, "alice")
    bob = await tasks.get_or_create_user(session, "bob")
    task = await tasks.create_task(session, alice, "Секрет")
    with pytest.raises(tasks.TaskNotFound):
        await tasks.move_task(session, bob, task.id, Status.done)
