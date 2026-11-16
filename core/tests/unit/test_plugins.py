from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from shtab_core.models import PluginRecord
from shtab_core.services.errors import ConflictError, NotFoundError
from shtab_core.services.plugins import (
    Plugin,
    PluginFrontend,
    PluginManager,
    PluginMenuItem,
    PluginPage,
)
from shtab_core.uow import UnitOfWork


def manifest(frontend=True):
    return Plugin(
        id="tasks",
        name="Задачи",
        version="1.0.0",
        url="https://github.com/example/tasks",
        backend_entrypoint="shtab_tasks.plugin:register",
        frontend=(
            PluginFrontend(
                entry="frontend/index.js",
                pages=(PluginPage(path="/tasks", element="shtab-tasks"),),
                menu_items=(PluginMenuItem(slot="sidebar.main", title="Задачи", path="/tasks"),),
            )
            if frontend
            else None
        ),
    )


@pytest.mark.parametrize("frontend", [True, False])
async def test_register_persists_manifest_across_uow(session_factory, frontend):
    plugin = manifest(frontend)
    async with UnitOfWork(session_factory) as uow:
        record = await PluginManager(uow, AsyncMock()).register(plugin)
        assert record.id == plugin.id
        assert uow.plugins.session is uow.users.session

    async with UnitOfWork(session_factory) as uow:
        manager = PluginManager(uow, AsyncMock())
        record = await manager.get(plugin.id)
        assert record.version == plugin.version
        assert record.backend_entrypoint == plugin.backend_entrypoint
        assert await manager.list_all() == [record]
        if frontend:
            assert record.frontend["pages"] == [{"path": "/tasks", "element": "shtab-tasks"}]
            assert record.frontend["menu_items"][0]["slot"] == "sidebar.main"
        else:
            assert record.frontend is None
        await manager.unregister(plugin.id)

    async with UnitOfWork(session_factory) as uow:
        assert await PluginManager(uow, AsyncMock()).list_all() == []


async def test_duplicate_registration_preserves_existing_record(uow):
    manager = PluginManager(uow, AsyncMock())
    await manager.register(manifest())
    with pytest.raises(ConflictError):
        await manager.register(manifest())
    assert len(await manager.list_all()) == 1


async def test_missing_plugin(uow):
    manager = PluginManager(uow, AsyncMock())
    with pytest.raises(NotFoundError):
        await manager.get("missing")
    with pytest.raises(NotFoundError):
        await manager.unregister("missing")


async def test_repository_never_flushes_or_commits(uow, monkeypatch):
    session = uow.plugins.session
    flush = AsyncMock(wraps=session.flush)
    commit = AsyncMock(wraps=session.commit)
    monkeypatch.setattr(session, "flush", flush)
    monkeypatch.setattr(session, "commit", commit)
    record = PluginRecord(
        id="tasks", name="Tasks", version="1", url="url", backend_entrypoint="tasks:register"
    )
    await uow.plugins.add(record)
    assert await uow.plugins.list_all() == []
    flush.assert_not_awaited()
    commit.assert_not_awaited()
    await uow.flush()
    await uow.plugins.delete(record)
    assert flush.await_count == 1
    commit.assert_not_awaited()


async def test_registration_failure_rolls_back(uow, monkeypatch):
    async def failed_commit():
        await uow.flush()
        raise IntegrityError("insert", {}, Exception("database error"))

    monkeypatch.setattr(uow.plugins.session, "commit", failed_commit)
    with pytest.raises(IntegrityError):
        await PluginManager(uow, AsyncMock()).register(manifest())
    assert await uow.plugins.list_all() == []
