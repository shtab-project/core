from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from shtab_core.uow import UnitOfWork


async def add_user(uow, sub="alice"):
    user = await uow.users.create(sub)
    await uow.users.update_profile(
        user, username=sub, name=sub, email=None, last_login_at=datetime.now(UTC)
    )
    return user


async def test_repository_operations_never_flush_or_end_session(uow, monkeypatch):
    session = uow.users.session
    spies = {}
    for method in ("flush", "commit", "rollback", "close"):
        spy = AsyncMock(wraps=getattr(session, method))
        monkeypatch.setattr(session, method, spy)
        spies[method] = spy
    user = await add_user(uow)
    project = await uow.projects.create("Project")
    await uow.organizations.create("Org")
    await uow.users.update_roles(user, is_admin=True)
    await uow.projects.update(project, description="Updated")
    assert await uow.projects.add_member(project, user)
    assert await uow.users.list() == []
    assert await uow.projects.list() == []
    assert await uow.organizations.get() is None
    assert user.id is None and project.id is None
    for spy in spies.values():
        spy.assert_not_awaited()
    # Записывать может только явный вызов через UoW.
    await uow.flush()
    assert user.id.version == 7
    assert await uow.projects.remove_member(project, user.id)
    await uow.projects.delete(project)
    assert spies["flush"].await_count == 1
    for method in ("commit", "rollback", "close"):
        spies[method].assert_not_awaited()


@pytest.mark.parametrize("fail", [False, True])
async def test_exit_rolls_back_uncommitted_work_and_closes(session_factory, fail):
    uow = UnitOfWork(session_factory)
    try:
        async with uow:
            session = uow.users.session
            session.close = AsyncMock(wraps=session.close)
            session.rollback = AsyncMock(wraps=session.rollback)
            assert session is uow.organizations.session is uow.projects.session
            await add_user(uow)
            await uow.organizations.create("Org")
            await uow.projects.create("Project")
            await uow.flush()
            if fail:
                raise ValueError("failed scenario")
    except ValueError:
        assert fail
    session.close.assert_awaited_once()
    session.rollback.assert_awaited_once()
    async with UnitOfWork(session_factory) as check:
        assert await check.users.list() == []
        assert await check.organizations.get() is None
        assert await check.projects.list() == []


async def test_explicit_commit_persists_all_repositories(session_factory):
    async with UnitOfWork(session_factory) as uow:
        user = await add_user(uow)
        project = await uow.projects.create("Project")
        await uow.organizations.create("Org")
        await uow.projects.add_member(project, user)
        await uow.commit()
        user_id, project_id = user.id, project.id
    async with UnitOfWork(session_factory) as check:
        assert await check.users.get(user_id) is not None
        assert await check.organizations.get() is not None
        assert (await check.projects.get(project_id)).users[0].id == user_id


async def test_failed_commit_rolls_back_whole_transaction(session_factory):
    with pytest.raises(IntegrityError):
        async with UnitOfWork(session_factory) as uow:
            await add_user(uow, "duplicate")
            await add_user(uow, "duplicate")
            await uow.organizations.create("Org")
            await uow.commit()
    async with UnitOfWork(session_factory) as check:
        assert await check.users.list() == []
        assert await check.organizations.get() is None


async def test_closed_uow_rejects_transaction_methods(session_factory):
    uow = UnitOfWork(session_factory)
    async with uow:
        pass
    for method in (uow.flush, uow.commit, uow.rollback):
        with pytest.raises(RuntimeError, match="async with"):
            await method()
