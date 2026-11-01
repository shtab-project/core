from sqlalchemy.exc import IntegrityError

from shtab_core.models import Organization, User
from shtab_core.services.errors import ConflictError
from shtab_core.uow import UnitOfWork


class SetupService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def get_organization(self) -> Organization | None:
        return await self.uow.organizations.get()

    async def setup(self, name: str, user: User) -> Organization:
        if await self.uow.organizations.get():
            raise ConflictError("Shtab уже настроен")
        try:
            organization = await self.uow.organizations.create(name)
            await self.uow.users.update_roles(user, is_admin=True, is_trusted=True)
            await self.uow.commit()
        except IntegrityError:
            # При одновременной настройке откатываем и организацию, и роли.
            await self.uow.rollback()
            raise ConflictError("Shtab уже настроен") from None
        return organization
