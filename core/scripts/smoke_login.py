"""Сквозная проверка входа через настоящий Authentik.

1. Создаёт в Authentik временного пользователя со случайным паролем (через API, токен akadmin).
2. Проходит вход как браузер: /api/auth/login → Authentik (логин + пароль) → /api/auth/callback.
3. Проверяет, что /api/me возвращает этого пользователя.
4. Удаляет временного пользователя из Authentik и из ядра.

Мастер первой настройки НЕ запускается — организация и администратор не создаются.
Запуск (стек должен быть поднят):  uv run python scripts/smoke_login.py
"""

import secrets
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit

import httpx

# Резолвер Windows (в отличие от браузеров) не знает *.localhost — направляем на 127.0.0.1.
_getaddrinfo = socket.getaddrinfo


def _localhost_getaddrinfo(host, *args, **kwargs):
    if isinstance(host, str) and host.endswith(".localhost"):
        host = "127.0.0.1"
    return _getaddrinfo(host, *args, **kwargs)


socket.getaddrinfo = _localhost_getaddrinfo

INFRA_ENV = Path(__file__).resolve().parents[2] / "infra" / ".env"
env = dict(line.split("=", 1) for line in INFRA_ENV.read_text("utf-8").splitlines() if "=" in line)
SHTAB = env.get("SHTAB_PUBLIC_URL", "http://shtab.localhost")
AUTH = env.get("SHTAB_AUTH_URL", "http://auth.shtab.localhost")
API = f"{AUTH}/api/v3"
ADMIN = {"Authorization": f"Bearer {env['AUTHENTIK_BOOTSTRAP_TOKEN']}"}

username = f"smoke-{secrets.token_hex(4)}"
password = secrets.token_urlsafe(24)


def step(msg: str) -> None:
    print(f"• {msg}")


def follow(client: httpx.Client, url: str, stop_host: str | None = None) -> str:
    """Идти по редиректам; остановиться на странице потока Authentik или на stop_host."""
    while True:
        r = client.get(url, follow_redirects=False)
        if r.status_code not in (301, 302, 303, 307, 308):
            return url
        url = urljoin(url, r.headers["location"])
        if "/if/flow/" in url or (stop_host and urlsplit(url).netloc == stop_host):
            return url


def run_flow(client: httpx.Client, flow_url: str) -> str:
    """Пройти поток входа Authentik через его API. Вернуть, куда он отправляет дальше."""
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
            sys.exit(f"Неожиданный шаг входа: {component} {challenge.get('response_errors', '')}")
        # После POST Authentik отвечает 302 на тот же executor со следующим шагом
        challenge = client.post(executor, json=body, follow_redirects=True).json()
    sys.exit("Поток входа не завершился")


def main() -> None:
    admin = httpx.Client(headers=ADMIN, timeout=30)
    user = (
        admin.post(
            f"{API}/core/users/",
            json={"username": username, "name": "Smoke Test", "email": f"{username}@example.test"},
        )
        .raise_for_status()
        .json()
    )
    admin.post(f"{API}/core/users/{user['pk']}/set_password/", json={"password": password})
    step(f"в Authentik создан временный пользователь {username}")

    try:
        browser = httpx.Client(timeout=30)
        flow_url = follow(browser, f"{SHTAB}/api/auth/login?next=/api/me")
        step("ядро отправило на вход в Authentik")
        after_login = run_flow(browser, flow_url)
        step("логин и пароль приняты Authentik")
        final = browser.get(after_login, follow_redirects=True)
        me = final.json()
        assert me["user"]["username"] == username, me
        step(f"/api/me → {me['user']['username']}, admin={me['user']['is_admin']}")
        assert "shtab_session" in browser.cookies
        step("сессия ядра выдана (cookie shtab_session)")
        print("OK: вход через Authentik работает")
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
        step("временный пользователь удалён из Authentik и ядра")


if __name__ == "__main__":
    main()
