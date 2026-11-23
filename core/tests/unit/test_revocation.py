"""Disabling a user revokes sessions and MCP tokens and blocks login."""

import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import pytest
from fastapi.responses import RedirectResponse
from httpx import ASGITransport, AsyncClient

from shtab_core.db import get_session_factory
from shtab_core.dependencies import get_plugin_loader
from shtab_core.main import app
from shtab_core.mcp_auth import MCPAuth, McpStorage, get_mcp_tokens
from shtab_core.mcp_gateway import ActiveUsers
from shtab_core.oidc import get_oidc
from shtab_core.sessions import SessionStore, get_sessions


@dataclass
class FakeOidc:
    claims: dict[str, object] = field(
        default_factory=lambda: {"sub": "alice", "preferred_username": "alice"}
    )

    async def authorize_redirect(self, request, redirect_uri):
        return RedirectResponse(
            f"https://auth.example/authorize?redirect_uri={redirect_uri}"
        )

    async def authorize_access_token(self, request):
        return {"userinfo": self.claims}

    async def load_server_metadata(self):
        return {"end_session_endpoint": "https://auth.example/logout"}


def seconds(ex: int | timedelta) -> int:
    return int(ex.total_seconds()) if isinstance(ex, timedelta) else ex


@dataclass
class FakeRedis:
    """The subset of redis.asyncio.Redis used by the session and token stores."""

    values: dict[str, Any] = field(default_factory=dict)
    ttls: dict[str, int] = field(default_factory=dict)

    async def set(self, key, value, ex=None):
        self.values[key] = value
        if ex:
            self.ttls[key] = seconds(ex)

    async def get(self, key):
        return self.values.get(key)

    async def sadd(self, key, *members):
        self.values.setdefault(key, set()).update(members)

    async def smembers(self, key):
        return set(self.values.get(key, set()))

    async def srem(self, key, *members):
        self.values.get(key, set()).difference_update(members)

    async def expire(self, key, ex):
        self.ttls[key] = seconds(ex)

    async def ttl(self, key):
        return self.ttls.get(key, -1) if key in self.values else -2

    async def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.ttls.pop(key, None)

    def pipeline(self, transaction=True):
        return FakePipeline(self)


@dataclass
class FakePipeline:
    client: FakeRedis
    calls: list = field(default_factory=list)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    def __getattr__(self, name):
        def queue(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return queue

    async def execute(self):
        for name, args, kwargs in self.calls:
            await getattr(self.client, name)(*args, **kwargs)


@pytest.fixture
def fake_redis():
    return FakeRedis()


async def test_session_store_revokes_all_user_sessions(fake_redis):
    store = SessionStore(fake_redis, ttl=60)
    alice, bob = uuid.uuid4(), uuid.uuid4()
    first, second = await store.create(alice), await store.create(alice)
    other = await store.create(bob)
    await store.revoke_user(alice)
    assert await store.get(first) is None and await store.get(second) is None
    assert await store.get(other) == bob


async def test_token_store_lists_revokes_and_rejects_forgery(fake_redis):
    tokens = McpStorage(fake_redis, ttl=timedelta(seconds=60))
    alice, bob = uuid.uuid4(), uuid.uuid4()
    first, second = (await tokens(alice)).value, (await tokens(alice)).value
    bobs = (await tokens(bob)).value
    first_id, second_id = tokens.token_id(first), tokens.token_id(second)
    assert {token.id for token in await tokens.list_for(alice)} == {first_id, second_id}
    assert await tokens.owner(first) == alice
    assert await tokens.owner(first[:-1] + ("A" if first[-1] != "A" else "B")) is None
    assert await tokens.owner("garbage") is None
    assert not await tokens.revoke(bob, first_id)
    assert await tokens.revoke(alice, first_id)
    assert await tokens.owner(first) is None
    assert [token.id for token in await tokens.list_for(alice)] == [second_id]
    await tokens.revoke_user(alice)
    assert await tokens.list_for(alice) == []
    assert await tokens.owner(bobs) == bob


@pytest.fixture
async def api(session_factory, fake_redis):
    sessions = SessionStore(fake_redis, ttl=60)
    tokens = McpStorage(fake_redis, ttl=timedelta(seconds=60))
    oidc = FakeOidc()
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_sessions] = lambda: sessions
    app.dependency_overrides[get_mcp_tokens] = lambda: tokens
    app.dependency_overrides[get_oidc] = lambda: oidc
    app.dependency_overrides[get_plugin_loader] = lambda: None
    transport = ASGITransport(app=app)

    async with (
        AsyncClient(transport=transport, base_url="http://shtab.localhost") as admin,
        AsyncClient(transport=transport, base_url="http://shtab.localhost") as member,
    ):
        yield admin, member, oidc, tokens

    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


async def test_disabling_user_revokes_access(api):
    admin, member, oidc, tokens = api
    await admin.get("/api/auth/callback")
    await admin.post("/api/setup", json={"organization_name": "Org"})
    admin_id = (await admin.get("/api/me")).json()["user"]["id"]

    oidc.claims = {"sub": "bob", "preferred_username": "bob"}
    await member.get("/api/auth/callback")
    member_id = (await member.get("/api/me")).json()["user"]["id"]
    token = (await member.post("/api/me/mcp-tokens")).json()["token"]
    assert len((await member.get("/api/me/mcp-tokens")).json()) == 1
    verifier = MCPAuth(storage=tokens, is_active=ActiveUsers(app))
    access = await verifier.verify_token(token)
    assert access and access.subject == member_id

    # Regular users cannot disable anyone; admins cannot disable themselves.
    assert (
        await member.patch(f"/api/users/{admin_id}", json={"is_active": False})
    ).status_code == 403
    assert (
        await admin.patch(f"/api/users/{admin_id}", json={"is_active": False})
    ).status_code == 409

    response = await admin.patch(f"/api/users/{member_id}", json={"is_active": False})
    assert response.status_code == 200 and response.json()["is_active"] is False
    assert (await member.get("/api/me")).status_code == 401
    assert await verifier.verify_token(token) is None
    assert await tokens.list_for(uuid.UUID(member_id)) == []
    assert (await member.get("/api/auth/callback")).status_code == 403
    assert (await member.get("/api/me")).status_code == 401

    # Reactivation allows a new login, but revoked credentials stay revoked.
    assert (
        await admin.patch(f"/api/users/{member_id}", json={"is_active": True})
    ).status_code == 200
    assert await verifier.verify_token(token) is None
    assert (await member.get("/api/auth/callback")).status_code == 303
    assert (await member.get("/api/me")).status_code == 200


async def test_token_routes_issue_list_and_revoke(api):
    _, member, oidc, _ = api
    oidc.claims = {"sub": "bob", "preferred_username": "bob"}
    await member.get("/api/auth/callback")
    issued = await member.post("/api/me/mcp-tokens")
    assert issued.status_code == 201
    assert issued.headers["cache-control"] == "no-store"
    token_id = issued.json()["id"]
    listed = (await member.get("/api/me/mcp-tokens")).json()
    assert [token["id"] for token in listed] == [token_id]
    assert (await member.delete(f"/api/me/mcp-tokens/{token_id}")).status_code == 204
    assert (await member.delete(f"/api/me/mcp-tokens/{token_id}")).status_code == 404
    assert (await member.get("/api/me/mcp-tokens")).json() == []


async def test_disabled_admin_does_not_count_as_last_admin(api):
    admin, member, oidc, _ = api
    await admin.get("/api/auth/callback")
    await admin.post("/api/setup", json={"organization_name": "Org"})
    admin_id = (await admin.get("/api/me")).json()["user"]["id"]
    oidc.claims = {"sub": "bob", "preferred_username": "bob"}
    await member.get("/api/auth/callback")
    member_id = (await member.get("/api/me")).json()["user"]["id"]
    assert (
        await admin.patch(f"/api/users/{member_id}", json={"is_admin": True})
    ).status_code == 200
    assert (
        await admin.patch(f"/api/users/{member_id}", json={"is_active": False})
    ).status_code == 200
    # Bob is disabled, so Alice is the last active admin.
    assert (
        await member.patch(f"/api/users/{admin_id}", json={"is_admin": False})
    ).status_code == 401
    assert (
        await admin.patch(f"/api/users/{admin_id}", json={"is_admin": False})
    ).status_code == 409
