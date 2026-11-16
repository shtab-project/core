"""Check OIDC discovery through the same network path used by the backend."""

import json
import time
from urllib.error import HTTPError
from urllib.request import urlopen

from shtab_core.config import settings


def main():
    discovery = settings.oidc_issuer + ".well-known/openid-configuration"
    for attempt in range(90):
        try:
            with urlopen(discovery, timeout=5) as response:
                metadata = json.load(response)
            if metadata["issuer"] != settings.oidc_issuer:
                raise ValueError("OIDC issuer отличается от настроенного адреса")
            with urlopen("http://127.0.0.1:8000/api/health", timeout=5) as response:
                assert json.load(response)["status"] == "ok"
            for plugin in ("todo", "notes"):
                try:
                    urlopen(f"http://127.0.0.1:8000/api/plugins/{plugin}/health", timeout=5)
                except HTTPError as error:
                    if error.code != 401:
                        raise
                else:
                    raise ValueError(f"{plugin}: endpoint unexpectedly allows anonymous access")
            print("OK: API, OIDC и оба плагина подключены; без входа плагины недоступны")
            return
        except (OSError, ValueError, KeyError) as error:
            if attempt == 89:
                raise RuntimeError(
                    "Authentik недоступен из ядра. Проверьте IP VPS и доступ к порту Authentik."
                ) from error
            time.sleep(2)


if __name__ == "__main__":
    main()
