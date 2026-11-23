"""SQLite checks: run with --confcutdir tests/unit, without PostgreSQL or Redis."""

import os

os.environ.setdefault("SHTAB_SECRET_KEY", "unit-test-secret")

import pytest  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from shtab_core import models  # noqa: E402, F401
from shtab_core.db import Base  # noqa: E402
from shtab_core.uow import UnitOfWork  # noqa: E402


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    await engine.dispose()


@pytest.fixture
async def session(session_factory):
    async with session_factory() as session:
        yield session


@pytest.fixture
async def uow(session_factory):
    async with UnitOfWork(session_factory) as uow:
        yield uow
