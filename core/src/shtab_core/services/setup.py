from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from shtab_core.exceptions import ConflictError
from shtab_core.models import Organization, User
from shtab_core.uow import UnitOfWork


@dataclass
class SetupService:
    uow: UnitOfWork

    async def get_organization(self) -> Organization | None:
        return await self.uow.organizations.get()

    async def setup(self, name: str, user: User) -> Organization:
        try:
            async with self.uow.transaction():
                if await self.uow.organizations.get():
                    raise ConflictError("Shtab is already set up")
                organization = await self.uow.organizations.create(name)
                await self.uow.users.update_roles(user, is_admin=True, is_trusted=True)
        except IntegrityError:
            raise ConflictError("Shtab is already set up") from None
        return organization
