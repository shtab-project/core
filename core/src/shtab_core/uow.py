from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shtab_core.repositories.organizations import OrganizationRepository
from shtab_core.repositories.plugins import PluginRepository
from shtab_core.repositories.projects import ProjectRepository
from shtab_core.repositories.users import UserRepository


class UnitOfWork:
    """One session for all repositories; save via commit or transaction."""

    users: UserRepository
    organizations: OrganizationRepository
    projects: ProjectRepository
    plugins: PluginRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        if self._session:
            raise RuntimeError("UnitOfWork is already open")
        self._session = self._session_factory(autoflush=False, expire_on_commit=False)
        self.users = UserRepository(self._session)
        self.organizations = OrganizationRepository(self._session)
        self.projects = ProjectRepository(self._session)
        self.plugins = PluginRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._get_session()
        try:
            # Roll back on a normal exit without commit and on an exception.
            if session.in_transaction():
                await session.rollback()
        finally:
            try:
                await session.close()
            finally:
                self._session = None

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession]:
        """Commit on success; otherwise roll back and re-raise the original error."""
        session = self._get_session()
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise

    def _get_session(self) -> AsyncSession:
        if not self._session:
            raise RuntimeError("Open UnitOfWork with async with")
        return self._session

    async def flush(self) -> None:
        await self._get_session().flush()

    async def commit(self) -> None:
        await self._get_session().commit()

    async def rollback(self) -> None:
        await self._get_session().rollback()
