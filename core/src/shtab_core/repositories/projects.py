from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shtab_core.models import Project, User


class ProjectRepository:
    """Проекты и участники. Транзакцию завершает вызывающий код."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, project_id: uuid.UUID) -> Project | None:
        query = select(Project).where(Project.id == project_id)
        query = query.options(selectinload(Project.users))
        return await self.session.scalar(query)

    async def list(self) -> list[Project]:
        projects = await self.session.scalars(
            select(Project)
            .options(selectinload(Project.users))
            .order_by(Project.created_at, Project.id)
        )
        return list(projects)

    async def list_for_user(self, user_id: uuid.UUID) -> list[Project]:
        projects = await self.session.scalars(
            select(Project)
            .where(Project.users.any(User.id == user_id))
            .options(selectinload(Project.users))
            .order_by(Project.created_at, Project.id)
        )
        return list(projects)

    async def create(self, name: str, description: str = "") -> Project:
        project = Project(name=name.strip(), description=description, users=[])
        self.session.add(project)
        return project

    async def update(
        self, project: Project, *, name: str | None = None, description: str | None = None
    ) -> Project:
        if name is not None:
            project.name = name.strip()
        if description is not None:
            project.description = description
        return project

    async def delete(self, project: Project) -> None:
        await self.session.delete(project)

    async def add_member(self, project: Project, user: User) -> bool:
        """Вернуть False, если пользователь уже участвует в проекте."""
        if user in project.users:
            return False
        project.users.append(user)
        return True

    async def remove_member(self, project: Project, user_id: uuid.UUID) -> bool:
        """Вернуть False, если пользователь не участвует в проекте."""
        member = next((user for user in project.users if user.id == user_id), None)
        if member is None:
            return False
        project.users.remove(member)
        return True
