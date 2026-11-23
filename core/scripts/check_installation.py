"""Check OIDC discovery through the same network path used by the backend."""

import asyncio
import json
import time
from urllib.error import HTTPError
from urllib.request import urlopen

import httpx2

from shtab_core.config import settings
from shtab_core.oidc import oauth


def main():
    for attempt in range(90):
        try:
            metadata = asyncio.run(oauth.authentik.load_server_metadata())
            if metadata["issuer"] != settings.oidc_issuer:
                raise ValueError("OIDC issuer differs from the configured URL")
            with urlopen("http://127.0.0.1:8000/api/health", timeout=5) as response:
                assert json.load(response)["status"] == "ok"
            for plugin in ("todo", "notes"):
                try:
                    urlopen(
                        f"http://127.0.0.1:8000/api/plugins/{plugin}/health", timeout=5
                    )
                except HTTPError as error:
                    if error.code != 401:
                        raise
                else:
                    raise ValueError(
                        f"{plugin}: endpoint unexpectedly allows anonymous access"
                    )
            print("OK: API, OIDC and both plugins are connected; plugins require login")
            return
        except (OSError, ValueError, KeyError, httpx2.HTTPError) as error:
            if attempt == 89:
                raise RuntimeError(
                    "Authentik is unreachable from the core. "
                    "Check the VPS IP and access to the Authentik port."
                ) from error
            time.sleep(2)


if __name__ == "__main__":
    main()
