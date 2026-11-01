from sqlalchemy.ext.asyncio import AsyncSession

from shtab_core.constants import ORGANIZATION_ID
from shtab_core.models import Organization


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self) -> Organization | None:
        return await self.session.get(Organization, ORGANIZATION_ID)

    async def create(self, name: str) -> Organization:
        organization = Organization(id=ORGANIZATION_ID, name=name.strip())
        self.session.add(organization)
        return organization
