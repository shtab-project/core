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
        project = await self.uow.projects.create(name, description)
        await self.uow.commit()
        return project

    async def update(
        self, project_id: uuid.UUID, *, name: str | None = None, description: str | None = None
    ) -> Project:
        project = await self.get(project_id)
        await self.uow.projects.update(project, name=name, description=description)
        await self.uow.commit()
        return project

    async def delete(self, project_id: uuid.UUID) -> None:
        await self.uow.projects.delete(await self.get(project_id))
        await self.uow.commit()

    async def add_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        project = await self.get(project_id)
        user = await self.uow.users.get(user_id)
        if user is None:
            raise NotFoundError("Пользователь не найден")
        added = await self.uow.projects.add_member(project, user)
        if added:
            await self.uow.commit()
        return added

    async def remove_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        project = await self.get(project_id)
        removed = await self.uow.projects.remove_member(project, user_id)
        if removed:
            await self.uow.commit()
        return removed
