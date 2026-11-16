"""Generate a separate, repeatable VPS configuration without copying local secrets."""

import argparse
import ipaddress
import os
import secrets
from pathlib import Path

SECRET_KEYS = (
    "PG_PASS",
    "SHTAB_DB_PASS",
    "REDIS_PASS",
    "AUTHENTIK_SECRET_KEY",
    "AUTHENTIK_BOOTSTRAP_PASSWORD",
    "AUTHENTIK_BOOTSTRAP_TOKEN",
    "SHTAB_OIDC_CLIENT_SECRET",
    "SHTAB_SECRET_KEY",
)


def configure(root: Path, host: str, port: int = 80, auth_port: int = 9000) -> Path:
    address = ipaddress.ip_address(host)
    if address.version != 4 or address.is_unspecified or address.is_multicast:
        raise ValueError("Укажите IPv4-адрес VPS")
    if not (1 <= port <= 65535 and 1 <= auth_port <= 65535) or port == auth_port:
        raise ValueError("Порты должны различаться и быть в диапазоне 1–65535")
    destination = root / "infra" / "vps"
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(destination, 0o700)
    target = destination / ".env"
    existing = {}
    if target.exists():
        for line in target.read_text("utf-8").splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                existing[key] = value
        for key in SECRET_KEYS:
            if not existing.get(key):
                raise ValueError(
                    f"В существующем {target} отсутствует {key}; восстановите конфигурацию"
                )
        if (
            existing.get("SHTAB_HOST") != host
            or existing.get("SHTAB_WEB_PORT") != str(port)
            or existing.get("SHTAB_AUTH_PORT") != str(auth_port)
        ):
            raise ValueError(
                "Адрес или порты отличаются от сохранённых. Используйте прежние параметры"
            )
    public = f"http://{host}" + (f":{port}" if port != 80 else "")
    auth = f"http://{host}:{auth_port}"
    values = {
        "SHTAB_HOST": host,
        "SHTAB_WEB_PORT": str(port),
        "SHTAB_AUTH_PORT": str(auth_port),
        "SHTAB_PUBLIC_URL": public,
        "SHTAB_AUTH_URL": auth,
        "AUTHENTIK_BOOTSTRAP_EMAIL": "admin@example.invalid",
        **{key: secrets.token_urlsafe(48) for key in SECRET_KEYS},
        **existing,
    }
    if not target.exists():
        with target.open("x", encoding="utf-8", newline="\n") as output:
            output.write("".join(f"{key}={value}\n" for key, value in values.items()))
    os.chmod(target, 0o600)
    blueprints = destination / "blueprints"
    blueprints.mkdir(exist_ok=True)
    template = (root / "infra/authentik/blueprints/shtab.yaml").read_text("utf-8")
    (blueprints / "shtab.yaml").write_text(
        template.replace("http://localhost:3000", values["SHTAB_PUBLIC_URL"]),
        encoding="utf-8",
        newline="\n",
    )
    credentials = destination / "credentials.txt"
    credentials.write_text(
        f"Shtab: {values['SHTAB_PUBLIC_URL']}\n"
        f"Authentik: {values['SHTAB_AUTH_URL']}/if/admin/\n"
        f"Login: akadmin\nPassword: {values['AUTHENTIK_BOOTSTRAP_PASSWORD']}\n",
        encoding="utf-8",
        newline="\n",
    )
    os.chmod(credentials, 0o600)
    return credentials


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--auth-port", type=int, default=9000)
    args = parser.parse_args()
    try:
        path = configure(
            Path(__file__).resolve().parents[2], args.host, args.port, args.auth_port
        )
    except ValueError as error:
        parser.error(str(error))
    print(f"Конфигурация готова. Данные входа: {path}")


if __name__ == "__main__":
    main()
