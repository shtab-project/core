from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shtab.models import Scope, Task, User
from shtab.notes.parser import ParsedTask, parse_tasks
from shtab.notes.spaces import iter_pages, space_root


async def reindex_space(session: AsyncSession, scope: Scope, owner: User | None) -> int:
    """Пересобрать индекс задач одного пространства. Возвращает число задач.

    id задачи сохраняется, если в том же файле нашлась та же строка (или задача
    с тем же заголовком) — так карточки канбана не «перерождаются» при правке
    соседних строк.
    """
    owner_id = owner.id if owner else None
    root = space_root(scope, owner.username if owner else None)

    parsed: list[tuple[str, ParsedTask]] = []
    for rel, file in iter_pages(root):
        parsed += [(rel, t) for t in parse_tasks(file.read_text("utf-8"))]

    owner_filter = Task.owner_id == owner_id if owner_id else Task.owner_id.is_(None)
    existing = (await session.scalars(select(Task).where(Task.scope == scope, owner_filter))).all()
    by_raw: dict[tuple[str, str], list[Task]] = defaultdict(list)
    by_title: dict[tuple[str, str], list[Task]] = defaultdict(list)
    for row in existing:
        by_raw[row.path, row.raw].append(row)
        by_title[row.path, row.title].append(row)

    used: set = set()
    for rel, t in parsed:
        row = _take(by_raw[rel, t.raw], used) or _take(by_title[rel, t.title], used)
        if row is None:
            row = Task(scope=scope, owner_id=owner_id, path=rel)
            session.add(row)
        used.add(id(row))
        row.line, row.raw, row.title = t.line, t.raw, t.title
        row.done, row.status, row.due, row.tags = t.done, t.status, t.due, t.tags

    for row in existing:
        if id(row) not in used:
            await session.delete(row)

    await session.commit()
    return len(parsed)


def _take(candidates: list[Task], used: set) -> Task | None:
    for row in candidates:
        if id(row) not in used:
            return row
    return None
