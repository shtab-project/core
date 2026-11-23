"""End-to-end login check against a real Authentik.

1. Creates a temporary Authentik user (API, akadmin token).
2. Logs in like a browser: /api/auth/login → Authentik → /api/auth/callback.
3. Checks that /api/me returns that user.
4. Deletes the temporary user from Authentik and the core.

The setup wizard is NOT run: no organization or admin is created.
Run (the stack must be up):  uv run python scripts/smoke_login.py
"""

import secrets
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit

import httpx

# The Windows resolver doesn't know *.localhost, so point it at 127.0.0.1.
_getaddrinfo = socket.getaddrinfo


def _localhost_getaddrinfo(host, *args, **kwargs):
    if isinstance(host, str) and host.endswith(".localhost"):
        host = "127.0.0.1"
    return _getaddrinfo(host, *args, **kwargs)


socket.getaddrinfo = _localhost_getaddrinfo

INFRA_ENV = Path(__file__).resolve().parents[2] / "infra" / ".env"
env = dict(
    line.split("=", 1)
    for line in INFRA_ENV.read_text("utf-8").splitlines()
    if "=" in line
)
SHTAB = env.get("SHTAB_PUBLIC_URL", "http://shtab.localhost")
AUTH = env.get("SHTAB_AUTH_URL", "http://auth.shtab.localhost")
API = f"{AUTH}/api/v3"
ADMIN = {"Authorization": f"Bearer {env['AUTHENTIK_BOOTSTRAP_TOKEN']}"}

username = f"smoke-{secrets.token_hex(4)}"
password = secrets.token_urlsafe(24)


def step(msg: str) -> None:
    print(f"• {msg}")


def follow(client: httpx.Client, url: str, stop_host: str | None = None) -> str:
    """Follow redirects up to the Authentik flow or stop_host."""
    while True:
        r = client.get(url, follow_redirects=False)
        if r.status_code not in (301, 302, 303, 307, 308):
            return url
        url = urljoin(url, r.headers["location"])
        if "/if/flow/" in url or (stop_host and urlsplit(url).netloc == stop_host):
            return url


def run_flow(client: httpx.Client, flow_url: str) -> str:
    """Run the Authentik login flow via API; return the next URL."""
    parts = urlsplit(flow_url)
    slug = parts.path.rstrip("/").split("/")[-1]
    executor = f"{API}/flows/executor/{slug}/?{urlencode({'query': parts.query})}"
    challenge = client.get(executor).json()
    for _ in range(10):
        component = challenge.get("component")
        if component == "xak-flow-redirect":
            return urljoin(AUTH, challenge["to"])
        if component == "ak-stage-identification":
            body = {"component": component, "uid_field": username}
            if challenge.get("password_fields"):
                body["password"] = password
        elif component == "ak-stage-password":
            body = {"component": component, "password": password}
        else:
            errors = challenge.get("response_errors", "")
            sys.exit(f"Unexpected login step: {component} {errors}")
        # After a POST, Authentik redirects to the same executor with the next step
        challenge = client.post(executor, json=body, follow_redirects=True).json()
    sys.exit("Login flow did not finish")


def main() -> None:
    admin = httpx.Client(headers=ADMIN, timeout=30)
    user = (
        admin.post(
            f"{API}/core/users/",
            json={
                "username": username,
                "name": "Smoke Test",
                "email": f"{username}@example.test",
            },
        )
        .raise_for_status()
        .json()
    )
    admin.post(
        f"{API}/core/users/{user['pk']}/set_password/", json={"password": password}
    )
    step(f"temporary Authentik user {username} created")

    try:
        browser = httpx.Client(timeout=30)
        flow_url = follow(browser, f"{SHTAB}/api/auth/login?next=/api/me")
        step("core redirected to the Authentik login")
        after_login = run_flow(browser, flow_url)
        step("Authentik accepted the username and password")
        final = browser.get(after_login, follow_redirects=True)
        me = final.json()
        assert me["user"]["username"] == username, me
        step(f"/api/me → {me['user']['username']}, admin={me['user']['is_admin']}")
        assert "shtab_session" in browser.cookies
        step("core session issued (shtab_session cookie)")
        print("OK: Authentik login works")
    finally:
        admin.delete(f"{API}/core/users/{user['pk']}/")
        subprocess.run(
            [
                "docker",
                "exec",
                "shtab-postgres-1",
                "psql",
                "-U",
                "postgres",
                "-d",
                "shtab",
                "-qc",
                f"DELETE FROM users WHERE username = '{username}'",
            ],
            check=False,
        )
        step("temporary user deleted from Authentik and the core")


if __name__ == "__main__":
    main()
