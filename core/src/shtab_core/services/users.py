from __future__ import annotations

import uuid

from shtab_core.models import Organization, User
from shtab_core.services.errors import ConflictError, NotFoundError
from shtab_core.uow import UnitOfWork


class UserService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def get_organization(self) -> Organization | None:
        return await self.uow.organizations.get()

    async def list(self) -> list[User]:
        return await self.uow.users.list()

    async def update_roles(
        self, user_id: uuid.UUID, *, is_admin: bool | None = None, is_trusted: bool | None = None
    ) -> User:
        async with self.uow.transaction():
            user = await self.uow.users.get(user_id)
            if user is None:
                raise NotFoundError("Пользователь не найден")
            if is_admin is False and user.is_admin:
                admin_count = await self.uow.users.count_admins()
                if admin_count == 1:
                    raise ConflictError("Нельзя снять последнего администратора")
            await self.uow.users.update_roles(user, is_admin=is_admin, is_trusted=is_trusted)
        return user
