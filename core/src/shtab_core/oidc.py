"""OIDC-клиент Authentik (приложение «Shtab»)."""

from typing import Annotated

from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App
from fastapi import Depends

from shtab_core.config import settings

oauth = OAuth()
oauth.register(
    "authentik",
    client_id=settings.oidc_client_id,
    client_secret=settings.oidc_client_secret,
    server_metadata_url=f"{settings.oidc_issuer}.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},  # PKCE
)


def get_oidc() -> StarletteOAuth2App:
    return oauth.authentik


Oidc = Annotated[StarletteOAuth2App, Depends(get_oidc)]
