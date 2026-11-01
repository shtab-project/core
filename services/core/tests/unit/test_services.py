import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from shtab_core.services.auth import AuthService
from shtab_core.services.errors import ConflictError, InvalidInputError, NotFoundError
from shtab_core.services.projects import ProjectService
from shtab_core.services.setup import SetupService
from shtab_core.services.users import UserService


@pytest.mark.parametrize("claims", [{}, {"sub": ""}, {"sub": 123}])
async def test_auth_requires_subject(uow, claims):
    with pytest.raises(InvalidInputError, match="нет sub"):
        await AuthService(uow).upsert_from_claims(claims)
    assert await uow.users.list() == []


async def test_login_preserves_roles_and_identity(uow):
    auth = AuthService(uow)
    user = await auth.upsert_from_claims({"sub": "alice", "name": "Алиса"})
    user_id = user.id
    await SetupService(uow).setup("Org", user)
    same = await auth.upsert_from_claims({"sub": "alice", "preferred_username": "new-name"})
    assert same.id == user_id and same.id.version == 7
    assert same.name == "new-name" and same.is_admin and same.is_trusted
    assert await uow.users.count_admins() == 1


async def test_setup_conflict_does_not_grant_roles(uow):
    auth = AuthService(uow)
    alice = await auth.upsert_from_claims({"sub": "alice"})
    await SetupService(uow).setup("Org", alice)
    bob = await auth.upsert_from_claims({"sub": "bob"})
    with pytest.raises(ConflictError):
        await SetupService(uow).setup("Other", bob)
    assert not bob.is_admin and not bob.is_trusted


async def test_setup_failed_commit_rolls_back_organization_and_roles(uow, monkeypatch):
    user = await AuthService(uow).upsert_from_claims({"sub": "alice"})
    user_id = user.id

    async def failed_commit():
        # Ошибка после записи, но до завершения общей транзакции.
        await uow.flush()
        raise IntegrityError("setup", {}, Exception("conflicting setup"))

    monkeypatch.setattr(uow, "commit", failed_commit)
    with pytest.raises(ConflictError):
        await SetupService(uow).setup("Org", user)
    assert await uow.organizations.get() is None
    reloaded = await uow.users.get(user_id)
    assert not reloaded.is_admin and not reloaded.is_trusted


async def test_last_admin_cannot_be_removed(uow):
    user = await AuthService(uow).upsert_from_claims({"sub": "alice"})
    await SetupService(uow).setup("Org", user)
    with pytest.raises(ConflictError):
        await UserService(uow).update_roles(user.id, is_admin=False)
    assert user.is_admin
    with pytest.raises(NotFoundError):
        await UserService(uow).update_roles(uuid.uuid4(), is_admin=True)


async def test_projects_commit_changes_and_membership(uow):
    user = await AuthService(uow).upsert_from_claims({"sub": "alice"})
    projects = ProjectService(uow)
    project = await projects.create("Project")
    assert project.id.version == 7
    assert await projects.add_member(project.id, user.id)
    assert not await projects.add_member(project.id, user.id)
    assert await projects.list_for_user(user.id) == [project]
    # Проверяем получение сгенерированного updated_at после UPDATE.
    project.updated_at = datetime(2000, 1, 1, tzinfo=UTC)
    await uow.flush()
    await projects.update(project.id, name="Updated")
    assert project.updated_at.year > 2000
    assert await projects.remove_member(project.id, user.id)
    assert not await projects.remove_member(project.id, user.id)
    assert await projects.list_for_user(user.id) == []
    await projects.delete(project.id)
    assert await projects.list() == []


async def test_project_membership_requires_existing_objects(uow):
    projects = ProjectService(uow)
    with pytest.raises(NotFoundError, match="Проект"):
        await projects.add_member(uuid.uuid4(), uuid.uuid4())
    project = await projects.create("Project")
    with pytest.raises(NotFoundError, match="Пользователь"):
        await projects.add_member(project.id, uuid.uuid4())
