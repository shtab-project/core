import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from shtab_core.db import Base
from shtab_core.models import Project, User, UsersXProjects
from shtab_core.repositories.organizations import OrganizationRepository
from shtab_core.repositories.projects import ProjectRepository
from shtab_core.repositories.users import UserRepository


async def create_user(session, sub="alice"):
    users = UserRepository(session)
    user = await users.create(sub)
    await users.update_profile(
        user, username=sub, name=sub, email=None, last_login_at=datetime.now(UTC)
    )
    await session.flush()
    return user


async def test_user_profile_update_keeps_identity_and_roles(session):
    users = UserRepository(session)
    user = await create_user(session)
    user_id = user.id
    assert user_id.version == 7
    assert user.username == "alice"
    assert await users.count_admins() == 0
    await users.update_roles(user, is_admin=True, is_trusted=True)
    await session.flush()
    same = await users.get_by_oidc_sub("alice")
    assert same
    await users.update_profile(
        same,
        username="new-name",
        name="new-name",
        email=None,
        last_login_at=datetime.now(UTC),
    )
    await session.flush()
    assert same.id == user_id
    assert same.name == "new-name"
    assert same.is_admin and same.is_trusted
    assert await users.count_admins() == 1
    assert await users.get(user_id) is same
    assert await users.list() == [same]


async def test_repositories_do_not_commit(session_factory):
    async with session_factory() as session:
        await create_user(session, "rolled-back")
        await OrganizationRepository(session).create("Org")
        await ProjectRepository(session).create("Project")
        await session.rollback()

    async with session_factory() as session:
        assert await UserRepository(session).list() == []
        assert await OrganizationRepository(session).get() is None
        assert await ProjectRepository(session).list() == []


async def test_single_organization(session):
    organizations = OrganizationRepository(session)
    assert await organizations.get() is None
    organization = await organizations.create("  Shtab  ")
    assert organization.id == 1
    assert organization.name == "Shtab"
    # A SELECT doesn't flush the new object automatically.
    assert await organizations.get() is None
    await session.flush()
    assert await organizations.get() is organization
    await session.commit()
    # Clear the identity map so the DB constraint itself is tested.
    session.expunge_all()
    with pytest.raises(IntegrityError):
        await organizations.create("Second")
        await session.flush()
    await session.rollback()


async def test_project_membership_and_update(session):
    projects = ProjectRepository(session)
    user = await create_user(session)
    project = await projects.create("  Project  ")
    await session.flush()
    assert project.id.version == 7
    assert project.name == "Project" and project.description == ""
    assert await projects.list_for_user(user.id) == []
    assert await projects.add_member(project, user)
    assert not await projects.add_member(project, user)
    await session.flush()
    assert await projects.list_for_user(user.id) == [project]
    loaded = await projects.get(project.id)
    assert loaded and loaded.users == [user]
    loaded_user = await session.scalar(
        select(User).options(selectinload(User.projects))
    )
    assert loaded_user.projects == [project]

    project.updated_at = datetime(2000, 1, 1, tzinfo=UTC)
    await session.flush()
    await projects.update(project, name="New name", description="Description")
    await session.flush()
    assert project.name == "New name" and project.description == "Description"
    assert project.updated_at.year > 2000
    assert await projects.remove_member(project, user.id)
    assert not await projects.remove_member(project, user.id)
    await session.flush()
    assert loaded_user.projects == []
    assert await projects.list_for_user(user.id) == []
    loaded = await projects.get(project.id)
    assert loaded and loaded.users == []


@pytest.mark.parametrize("delete_user", [False, True])
async def test_deletion_cascades_only_memberships(session, delete_user):
    projects = ProjectRepository(session)
    user = await create_user(session)
    project = await projects.create("Project")
    await session.flush()
    assert await projects.add_member(project, user)
    user_id, project_id = user.id, project.id
    await session.commit()
    session.expunge_all()
    if delete_user:
        await session.delete(await session.get(User, user_id))
    else:
        await projects.delete(await session.get(Project, project_id))
    await session.flush()
    assert await session.scalar(select(func.count()).select_from(UsersXProjects)) == 0
    survivor = Project if delete_user else User
    assert await session.scalar(select(func.count()).select_from(survivor)) == 1


async def test_membership_database_constraints(session):
    user = await create_user(session)
    project = await ProjectRepository(session).create("Project")
    await session.flush()
    await ProjectRepository(session).add_member(project, user)
    await session.commit()
    session.add(UsersXProjects(user_id=user.id, project_id=project.id))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


def test_migrations_match_models_and_are_reversible():
    directory = Path(__file__).resolve().parents[2] / "migrations" / "versions"
    migrations = []
    for path in sorted(directory.glob("*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        migrations.append(module)

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            for migration in migrations:
                migration.upgrade()
            assert compare_metadata(context, Base.metadata) == []
            for migration in reversed(migrations):
                migration.downgrade()
        assert connection.dialect.get_table_names(connection) == []
    engine.dispose()
