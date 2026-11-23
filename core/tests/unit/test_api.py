import secrets
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.responses import RedirectResponse
from httpx import ASGITransport, AsyncClient

from shtab_core.db import get_session_factory
from shtab_core.dependencies import get_plugin_loader
from shtab_core.main import app
from shtab_core.oidc import get_oidc
from shtab_core.routers import plugin_ui
from shtab_core.sessions import get_sessions


def plugin_payload():
    return {
        "id": "tasks",
        "name": "Tasks",
        "version": "1.0.0",
        "url": "https://github.com/example/tasks",
        "backend_entrypoint": "shtab_tasks.plugin:register",
        "frontend": {
            "entry": "frontend/index.js",
            "pages": [{"path": "/tasks", "element": "shtab-tasks"}],
            "menu_items": [
                {"slot": "sidebar.main", "title": "Tasks", "path": "/tasks"}
            ],
        },
    }


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
        return RedirectResponse(
            f"https://auth.example/authorize?redirect_uri={redirect_uri}"
        )

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
    plugin_loader = AsyncMock()
    app.dependency_overrides[get_plugin_loader] = lambda: plugin_loader
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport, base_url="http://shtab.localhost"
    ) as client:
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
    response = await client.post("/api/setup", json={"organization_name": "  Shtab  "})
    assert response.status_code == 201
    assert response.json()["name"] == "Shtab"
    assert (await client.get("/api/setup")).json()["initialized"] is True
    assert (
        await client.post("/api/setup", json={"organization_name": "Other"})
    ).status_code == 409
    me = (await client.get("/api/me")).json()
    user_id = me["user"]["id"]
    assert me["user"]["is_admin"] and me["user"]["is_trusted"]
    assert (await client.get("/api/users")).json()[0]["id"] == user_id
    assert (
        await client.patch(f"/api/users/{user_id}", json={"is_admin": False})
    ).status_code == 409
    response = await client.patch(f"/api/users/{user_id}", json={"is_trusted": False})
    assert response.status_code == 200 and not response.json()["is_trusted"]

    oidc.claims["name"] = "Alice"
    assert (await client.get("/api/auth/callback")).status_code == 303
    me = (await client.get("/api/me")).json()["user"]
    assert me["id"] == user_id and me["name"] == "Alice" and me["is_admin"]
    assert not me["is_trusted"]
    assert (await client.post("/api/auth/logout")).status_code == 200
    assert (await client.get("/api/me")).status_code == 401


async def test_callback_missing_subject_is_bad_request(api):
    client, oidc = api
    oidc.claims = {}
    response = await client.get("/api/auth/callback")
    assert response.status_code == 400
    assert response.json()["detail"] == "Authentik response has no sub"
    assert (await client.get("/api/me")).status_code == 401


def test_openapi_dependency_graph():
    schema = app.openapi()
    assert "/api/setup" in schema["paths"]
    # Internal Depends parameters must not become query parameters.
    assert "parameters" not in schema["paths"]["/api/users"]["get"]


@pytest.mark.parametrize("signed_in,expected_status", [(False, 401), (True, 403)])
@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/plugins"),
        ("GET", "/api/plugins/tasks"),
        ("POST", "/api/plugins"),
        ("DELETE", "/api/plugins/tasks"),
    ],
)
async def test_plugin_routes_require_admin(
    api, signed_in, expected_status, method, path
):
    client, _ = api
    if signed_in:
        assert (await client.get("/api/auth/callback")).status_code == 303
    response = await client.request(
        method,
        path,
        json=plugin_payload() if method == "POST" else None,
        # Client-sent flags don't override the role from the DB.
        headers={"X-Is-Admin": "true"},
        params={"is_admin": "true"},
    )
    assert response.status_code == expected_status


async def test_admin_plugin_lifecycle_and_user_cannot_delete(api):
    client, oidc = api
    await client.get("/api/auth/callback")
    await client.post("/api/setup", json={"organization_name": "Org"})
    assert (await client.get("/api/plugins")).json() == []

    response = await client.post("/api/plugins", json=plugin_payload())
    assert response.status_code == 201, response.text
    plugin = response.json()
    assert plugin["frontend"]["pages"] == plugin_payload()["frontend"]["pages"]
    assert (await client.get("/api/plugins/tasks")).json() == plugin
    assert (await client.get("/api/plugins")).json() == [plugin]
    assert (await client.post("/api/plugins", json=plugin_payload())).status_code == 409
    assert (await client.get("/api/plugins/missing")).status_code == 404
    assert (await client.delete("/api/plugins/missing")).status_code == 404

    oidc.claims = {"sub": "bob", "preferred_username": "bob"}
    await client.get("/api/auth/callback")
    assert (await client.delete("/api/plugins/tasks")).status_code == 403

    oidc.claims = {"sub": "alice", "preferred_username": "alice"}
    await client.get("/api/auth/callback")
    assert (await client.get("/api/plugins/tasks")).status_code == 200
    response = await client.delete("/api/plugins/tasks")
    assert response.status_code == 204
    assert response.content == b""
    assert (await client.get("/api/plugins")).json() == []


async def test_catalog_install_errors_preserve_status_and_detail(api):
    client, _ = api
    await client.get("/api/auth/callback")
    await client.post("/api/setup", json={"organization_name": "Org"})
    path = "/api/plugins/catalog"

    missing = await client.post(f"{path}/missing/install")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Plugin not found in the catalog"}

    loader = app.dependency_overrides[get_plugin_loader]()
    loader.install.side_effect = OSError("Installation failed")
    failed = await client.post(f"{path}/todo/install")
    assert failed.status_code == 502
    assert failed.json() == {"detail": "Failed to install the plugin. Try again."}


@pytest.mark.parametrize(
    "changes",
    [
        {"id": " "},
        {"version": ""},
        {"name": "x" * 201},
        {"is_admin": True},
        {"frontend": {"entry": "frontend/index.js", "pages": [{"path": "/tasks"}]}},
    ],
)
async def test_plugin_registration_validates_manifest(api, changes):
    client, _ = api
    await client.get("/api/auth/callback")
    await client.post("/api/setup", json={"organization_name": "Org"})
    payload = plugin_payload() | changes
    response = await client.post("/api/plugins", json=payload)
    assert response.status_code == 422
    assert (await client.get("/api/plugins")).json() == []


def test_plugin_routes_openapi():
    paths = app.openapi()["paths"]
    assert "post" in paths["/api/plugins"]
    assert "delete" in paths["/api/plugins/{plugin_id}"]
    assert "parameters" not in paths["/api/plugins"]["post"]
    assert paths["/api/plugins"]["post"]["requestBody"]["required"]


async def test_plugin_ui_for_regular_user_and_private_assets(
    api, tmp_path, monkeypatch
):
    monkeypatch.setattr(plugin_ui, "paths", SimpleNamespace(plugins=tmp_path))
    frontend = tmp_path / "tasks" / "frontend"
    frontend.mkdir(parents=True)
    source = "import './chunk.js'; export const ready = true;"
    (frontend / "index.js").write_text(source)
    (frontend / "chunk.js").write_text("export const ready = true;")
    (tmp_path / "tasks" / "secret.json").write_text('{"secret": true}')
    client, oidc = api
    assert (await client.get("/api/plugin-ui")).status_code == 401
    assert (
        await client.get("/api/plugin-assets/tasks/frontend/index.js")
    ).status_code == 401
    await client.get("/api/auth/callback")
    await client.post("/api/setup", json={"organization_name": "Org"})
    assert (await client.post("/api/plugins", json=plugin_payload())).status_code == 201
    oidc.claims = {"sub": "bob", "preferred_username": "bob"}
    await client.get("/api/auth/callback")
    assert (await client.get("/api/plugins")).status_code == 403
    response = await client.get("/api/plugin-ui")
    assert response.status_code == 200, response.text
    plugin = response.json()[0]
    assert set(plugin) == {"id", "name", "version", "frontend"}
    entry = plugin["frontend"]["entry"]
    assert entry == "/api/plugin-assets/tasks/frontend/index.js"
    response = await client.get(entry)
    assert response.status_code == 200 and response.text == source
    assert "javascript" in response.headers["content-type"]
    assert (
        await client.get("/api/plugin-assets/tasks/frontend/chunk.js")
    ).status_code == 200
    for path in ["secret.json", "frontend/%2e%2e%2fsecret.json", "frontend/missing.js"]:
        assert (await client.get(f"/api/plugin-assets/tasks/{path}")).status_code == 404
