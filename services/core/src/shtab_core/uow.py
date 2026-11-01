from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shtab_core.repositories.organizations import OrganizationRepository
from shtab_core.repositories.projects import ProjectRepository
from shtab_core.repositories.users import UserRepository


class UnitOfWork:
    """Одна сессия для всех репозиториев, сохранение только через явный commit."""

    users: UserRepository
    organizations: OrganizationRepository
    projects: ProjectRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        if self._session is not None:
            raise RuntimeError("UnitOfWork уже открыт")
        self._session = self._session_factory(autoflush=False, expire_on_commit=False)
        self.users = UserRepository(self._session)
        self.organizations = OrganizationRepository(self._session)
        self.projects = ProjectRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._get_session()
        try:
            # Откат нужен и при обычном выходе без commit, и при исключении.
            if session.in_transaction():
                await session.rollback()
        finally:
            try:
                await session.close()
            finally:
                self._session = None

    def _get_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UnitOfWork нужно открыть через async with")
        return self._session

    async def flush(self) -> None:
        await self._get_session().flush()

    async def commit(self) -> None:
        await self._get_session().commit()

    async def rollback(self) -> None:
        await self._get_session().rollback()
