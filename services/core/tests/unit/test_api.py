import secrets

import pytest
from fastapi.responses import RedirectResponse
from httpx import ASGITransport, AsyncClient

from shtab_core.db import get_session_factory
from shtab_core.main import app
from shtab_core.oidc import get_oidc
from shtab_core.sessions import get_sessions


class MemorySessions:
    def __init__(self):
        self.values = {}

    async def create(self, user_id):
        session_id = secrets.token_urlsafe(32)
        self.values[session_id] = user_id
        return session_id

    async def get(self, session_id):
        return self.values.get(session_id)

    async def delete(self, session_id):
        self.values.pop(session_id, None)


class FakeOidc:
    def __init__(self):
        self.claims = {"sub": "alice", "preferred_username": "alice"}

    async def authorize_redirect(self, request, redirect_uri):
        return RedirectResponse(f"https://auth.example/authorize?redirect_uri={redirect_uri}")

    async def authorize_access_token(self, request):
        return {"userinfo": self.claims}

    async def load_server_metadata(self):
        return {"end_session_endpoint": "https://auth.example/logout"}


@pytest.fixture
async def api(session_factory):
    sessions = MemorySessions()
    oidc = FakeOidc()

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_sessions] = lambda: sessions
    app.dependency_overrides[get_oidc] = lambda: oidc
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://shtab.localhost") as client:
        yield client, oidc
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


async def test_login_setup_roles_and_logout(api):
    client, oidc = api
    assert (await client.get("/api/setup")).json() == {
        "initialized": False,
        "organization": None,
    }
    assert (await client.get("/api/me")).status_code == 401
    response = await client.get("/api/auth/callback")
    assert response.status_code == 303
    assert "HttpOnly" in response.headers["set-cookie"]
    assert (await client.get("/api/users")).status_code == 403
    response = await client.post("/api/setup", json={"organization_name": "  Штаб  "})
    assert response.status_code == 201
    assert response.json()["name"] == "Штаб"
    assert (await client.get("/api/setup")).json()["initialized"] is True
    assert (await client.post("/api/setup", json={"organization_name": "Other"})).status_code == 409
    me = (await client.get("/api/me")).json()
    user_id = me["user"]["id"]
    assert me["user"]["is_admin"] and me["user"]["is_trusted"]
    assert (await client.get("/api/users")).json()[0]["id"] == user_id
    assert (
        await client.patch(f"/api/users/{user_id}", json={"is_admin": False})
    ).status_code == 409
    response = await client.patch(f"/api/users/{user_id}", json={"is_trusted": False})
    assert response.status_code == 200 and not response.json()["is_trusted"]

    oidc.claims["name"] = "Алиса"
    assert (await client.get("/api/auth/callback")).status_code == 303
    me = (await client.get("/api/me")).json()["user"]
    assert me["id"] == user_id and me["name"] == "Алиса" and me["is_admin"]
    assert not me["is_trusted"]
    assert (await client.post("/api/auth/logout")).status_code == 200
    assert (await client.get("/api/me")).status_code == 401


async def test_callback_missing_subject_is_bad_request(api):
    client, oidc = api
    oidc.claims = {}
    response = await client.get("/api/auth/callback")
    assert response.status_code == 400
    assert response.json()["detail"] == "В ответе Authentik нет sub"
    assert (await client.get("/api/me")).status_code == 401


def test_openapi_dependency_graph():
    schema = app.openapi()
    assert "/api/setup" in schema["paths"]
    # Внутренние параметры Depends не должны становиться параметрами запроса.
    assert "parameters" not in schema["paths"]["/api/users"]["get"]
