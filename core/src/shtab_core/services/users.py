from __future__ import annotations

import uuid
from dataclasses import dataclass

from shtab_core.exceptions import ConflictError, NotFoundError
from shtab_core.models import Organization, User
from shtab_core.uow import UnitOfWork


@dataclass
class UserService:
    uow: UnitOfWork

    async def get_organization(self) -> Organization | None:
        return await self.uow.organizations.get()

    async def list(self) -> list[User]:
        return await self.uow.users.list()

    async def update_roles(
        self,
        user_id: uuid.UUID,
        *,
        is_admin: bool | None = None,
        is_trusted: bool | None = None,
        is_active: bool | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> User:
        async with self.uow.transaction():
            user = await self.uow.users.get(user_id)
            if not user:
                raise NotFoundError("User not found")
            if is_active is False and user.id == actor_id:
                raise ConflictError("You can't disable your own account")
            loses_admin = is_admin is False or is_active is False
            if loses_admin and user.is_admin and user.is_active:
                admin_count = await self.uow.users.count_admins()
                if admin_count == 1:
                    raise ConflictError("Can't demote or disable the last admin")
            await self.uow.users.update_roles(
                user, is_admin=is_admin, is_trusted=is_trusted, is_active=is_active
            )

        return user
