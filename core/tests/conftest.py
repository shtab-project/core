"""Core tests on real PostgreSQL (shtab_test database) and Redis (db 15).

The base stack must be running: docker compose up -d (in infra/).
The DB password comes from infra/.env; SHTAB_TEST_DATABASE_URL overrides the URL.
"""

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
INFRA_ENV = CORE.parent / "infra" / ".env"


def _infra_env(key: str) -> str:
    for line in INFRA_ENV.read_text("utf-8").splitlines():
        name, sep, value = line.partition("=")
        if sep and name == key:
            return value
    raise RuntimeError(f"{key} is missing from {INFRA_ENV}")


os.environ["SHTAB_DATABASE_URL"] = os.environ.get("SHTAB_TEST_DATABASE_URL") or (
    f"postgresql+asyncpg://shtab:{_infra_env('SHTAB_DB_PASS')}@localhost:5432/shtab_test"
)
os.environ["SHTAB_REDIS_URL"] = f"redis://:{_infra_env('REDIS_PASS')}@localhost:6379/15"
os.environ["SHTAB_SECRET_KEY"] = "test-secret"
os.environ["SHTAB_PUBLIC_URL"] = "http://shtab.localhost"

import pytest  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from shtab_core.db import engine  # noqa: E402
from shtab_core.main import app  # noqa: E402
from shtab_core.oidc import get_oidc  # noqa: E402
from shtab_core.sessions import redis  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    """Run migrations down and up, which also checks they are reversible."""
    for command, target in (("downgrade", "base"), ("upgrade", "head")):
        subprocess.run(
            [sys.executable, "-m", "alembic", command, target],
            cwd=CORE,
            env=os.environ,
            check=True,
            capture_output=True,
        )


@pytest.fixture(autouse=True)
async def clean_state(migrated_db):
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE plugins, users_projects, projects, users, organization")
        )

    await redis.flushdb()
    yield


@dataclass
class FakeOidc:
    """Fake Authentik: the callback returns a user with the given claims."""

    claims: dict[str, object] = field(default_factory=dict)

    async def authorize_redirect(self, request, redirect_uri):
        return RedirectResponse(
            f"http://auth.shtab.localhost/authorize?redirect_uri={redirect_uri}"
        )

    async def authorize_access_token(self, request):
        return {"userinfo": self.claims}

    async def load_server_metadata(self):
        return {"end_session_endpoint": "http://auth.shtab.localhost/end-session/"}


@pytest.fixture
def oidc():
    fake = FakeOidc()
    app.dependency_overrides[get_oidc] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def new_client(oidc):
    """Client factory: each client is a separate browser with its own cookies."""

    @asynccontextmanager
    async def factory() -> AsyncIterator[AsyncClient]:
        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport, base_url="http://shtab.localhost"
        ) as client:
            yield client

    return factory


@pytest.fixture
def login(oidc):
    async def do_login(client: AsyncClient, username: str, name: str | None = None):
        oidc.claims = {
            "sub": f"sub-{username}",
            "preferred_username": username,
            "name": name or username.title(),
            "email": f"{username}@example.test",
        }
        response = await client.get("/api/auth/callback")
        assert response.status_code == 303, response.text
        return response

    return do_login
