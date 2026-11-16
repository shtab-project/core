from shtab_core.constants import DEFAULT_NEXT
from shtab_core.routers.auth import safe_next


def test_safe_next_blocks_open_redirect():
    assert safe_next("/projects/1") == "/projects/1"
    for bad in (None, "", "https://evil.example", "//evil.example", "/\\evil.example"):
        assert safe_next(bad) == DEFAULT_NEXT


async def test_login_redirects_to_authentik(new_client):
    async with new_client() as client:
        r = await client.get("/api/auth/login", params={"next": "/projects"})
        assert r.status_code in (302, 307)
        assert r.headers["location"].startswith("http://auth.shtab.localhost/authorize")


async def test_callback_sets_secure_session_cookie(new_client, login):
    async with new_client() as client:
        r = await login(client, "alice")
        cookie = r.headers["set-cookie"]
        assert (
            "shtab_session=" in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()
        )
        assert r.headers["location"] == DEFAULT_NEXT


async def test_first_setup_makes_admin(new_client, login):
    async with new_client() as alice, new_client() as bob:
        assert (await alice.get("/api/setup")).json() == {
            "initialized": False,
            "organization": None,
        }
        assert (await alice.post("/api/setup", json={"organization_name": "X"})).status_code == 401

        await login(alice, "alice")
        r = await alice.post("/api/setup", json={"organization_name": "  Тестовая организация "})
        assert r.status_code == 201
        assert r.json()["name"] == "Тестовая организация"

        me = (await alice.get("/api/me")).json()
        assert me["user"]["is_admin"] and me["user"]["is_trusted"]
        assert me["organization"]["name"] == "Тестовая организация"
        assert (await alice.get("/api/setup")).json()["initialized"] is True

        # Повторно настроить нельзя — ни тому же, ни другому
        assert (await alice.post("/api/setup", json={"organization_name": "Y"})).status_code == 409
        await login(bob, "bob")
        assert (await bob.post("/api/setup", json={"organization_name": "Z"})).status_code == 409
        bob_me = (await bob.get("/api/me")).json()["user"]
        assert not bob_me["is_admin"] and not bob_me["is_trusted"]


async def test_relogin_updates_profile_keeps_id(new_client, login):
    async with new_client() as client:
        await login(client, "alice", name="Алиса")
        first = (await client.get("/api/me")).json()["user"]
        await login(client, "alice", name="Алиса Иванова")
        second = (await client.get("/api/me")).json()["user"]
        assert second["id"] == first["id"]
        assert second["name"] == "Алиса Иванова"


async def test_logout_kills_session(new_client, login):
    async with new_client() as client:
        await login(client, "alice")
        stolen_cookie = client.cookies["shtab_session"]
        r = await client.post("/api/auth/logout")
        assert r.json()["logout_url"] == "http://auth.shtab.localhost/end-session/"
        assert (await client.get("/api/me")).status_code == 401
        # Старая cookie после выхода больше не работает (сессия удалена в Redis)
        client.cookies.set("shtab_session", stolen_cookie)
        assert (await client.get("/api/me")).status_code == 401


async def test_unknown_session_is_rejected(new_client):
    async with new_client() as client:
        client.cookies.set("shtab_session", "forged")
        assert (await client.get("/api/me")).status_code == 401


async def test_admin_manages_roles(new_client, login):
    async with new_client() as alice, new_client() as bob:
        await login(alice, "alice")
        await alice.post("/api/setup", json={"organization_name": "Org"})
        await login(bob, "bob")

        assert (await bob.get("/api/users")).status_code == 403
        users = {u["username"]: u for u in (await alice.get("/api/users")).json()}
        assert set(users) == {"alice", "bob"}

        bob_id, alice_id = users["bob"]["id"], users["alice"]["id"]
        assert (await bob.patch(f"/api/users/{bob_id}", json={"is_admin": True})).status_code == 403

        r = await alice.patch(f"/api/users/{bob_id}", json={"is_trusted": True})
        assert r.status_code == 200 and r.json()["is_trusted"] and not r.json()["is_admin"]

        # Последнего администратора снять нельзя
        r = await alice.patch(f"/api/users/{alice_id}", json={"is_admin": False})
        assert r.status_code == 409

        await alice.patch(f"/api/users/{bob_id}", json={"is_admin": True})
        r = await alice.patch(f"/api/users/{alice_id}", json={"is_admin": False})
        assert r.status_code == 200 and not r.json()["is_admin"]
        assert (await alice.get("/api/users")).status_code == 403
