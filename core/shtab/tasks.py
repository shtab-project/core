"""Операции над задачами. Общие для REST API, MCP-инструментов и воркера."""

import asyncio
import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shtab.models import Scope, Status, Task, User
from shtab.notes.indexer import reindex_space
from shtab.notes.parser import TaskConflict, append_task, set_status
from shtab.notes.spaces import INBOX, safe_join, space_root

__all__ = ["TaskConflict", "TaskNotFound", "create_task", "list_tasks", "move_task"]

# Запись в файлы — только последовательно в пределах процесса.
# TODO: при нескольких репликах ядра заменить на блокировку в Redis.
_write_lock = asyncio.Lock()


class TaskNotFound(Exception):
    pass


async def get_or_create_user(session: AsyncSession, username: str) -> User:
    user = await session.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(username=username)
        session.add(user)
        await session.commit()
    return user


def _visible_to(user: User):
    return or_(
        Task.scope == Scope.shared, and_(Task.scope == Scope.personal, Task.owner_id == user.id)
    )


async def list_tasks(
    session: AsyncSession, user: User, scope: Scope | None = None, status: Status | None = None
) -> Sequence[Task]:
    query = select(Task).where(_visible_to(user))
    if scope:
        query = query.where(Task.scope == scope)
    if status:
        query = query.where(Task.status == status)
    query = query.order_by(Task.due.asc().nulls_last(), Task.path, Task.line)
    return (await session.scalars(query)).all()


async def create_task(
    session: AsyncSession,
    user: User,
    title: str,
    scope: Scope = Scope.personal,
    due: date | None = None,
    tags: list[str] | None = None,
) -> Task:
    """Дописать задачу во «Входящие» нужного пространства."""
    owner = user if scope is Scope.personal else None
    inbox = space_root(scope, user.username) / INBOX
    async with _write_lock:
        text = inbox.read_text("utf-8") if inbox.exists() else "# Входящие\n\n"
        new_text, line = append_task(text, title, due=due, tags=tags)
        inbox.parent.mkdir(parents=True, exist_ok=True)
        inbox.write_text(new_text, "utf-8", newline="\n")
    await reindex_space(session, scope, owner)
    return await _task_at(session, scope, owner, INBOX, line)


async def move_task(session: AsyncSession, user: User, task_id: uuid.UUID, status: Status) -> Task:
    """Сменить статус (колонку канбана) и записать изменение в markdown."""
    task = await session.scalar(select(Task).where(Task.id == task_id, _visible_to(user)))
    if task is None:
        raise TaskNotFound(task_id)
    owner = user if task.scope is Scope.personal else None
    file = safe_join(space_root(task.scope, user.username), task.path)
    async with _write_lock:
        new_text = set_status(file.read_text("utf-8"), task.line, task.raw, status)
        file.write_text(new_text, "utf-8", newline="\n")
    await reindex_space(session, task.scope, owner)
    await session.refresh(task)
    return task


async def _task_at(
    session: AsyncSession, scope: Scope, owner: User | None, path: str, line: int
) -> Task:
    owner_filter = Task.owner_id == owner.id if owner else Task.owner_id.is_(None)
    task = await session.scalar(
        select(Task).where(Task.scope == scope, owner_filter, Task.path == path, Task.line == line)
    )
    if task is None:
        raise TaskNotFound(f"{path}:{line}")
    return task
