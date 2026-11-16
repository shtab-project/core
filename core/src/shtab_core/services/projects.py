from __future__ import annotations

import uuid

from shtab_core.models import Project
from shtab_core.services.errors import NotFoundError
from shtab_core.uow import UnitOfWork


class ProjectService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def get(self, project_id: uuid.UUID) -> Project:
        project = await self.uow.projects.get(project_id)
        if project is None:
            raise NotFoundError("Проект не найден")
        return project

    async def list(self) -> list[Project]:
        return await self.uow.projects.list()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Project]:
        return await self.uow.projects.list_for_user(user_id)

    async def create(self, name: str, description: str = "") -> Project:
        async with self.uow.transaction():
            project = await self.uow.projects.create(name, description)
        return project

    async def update(
        self, project_id: uuid.UUID, *, name: str | None = None, description: str | None = None
    ) -> Project:
        async with self.uow.transaction():
            project = await self.get(project_id)
            await self.uow.projects.update(project, name=name, description=description)
        return project

    async def delete(self, project_id: uuid.UUID) -> None:
        async with self.uow.transaction():
            await self.uow.projects.delete(await self.get(project_id))

    async def add_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        async with self.uow.transaction():
            project = await self.get(project_id)
            user = await self.uow.users.get(user_id)
            if user is None:
                raise NotFoundError("Пользователь не найден")
            added = await self.uow.projects.add_member(project, user)
        return added

    async def remove_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        async with self.uow.transaction():
            project = await self.get(project_id)
            removed = await self.uow.projects.remove_member(project, user_id)
        return removed
