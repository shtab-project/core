"""OIDC-клиент Authentik (приложение «Shtab»)."""

from typing import Annotated

import httpx2
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App
from fastapi import Depends

from shtab_core.config import settings


class AuthentikTransport(httpx2.AsyncHTTPTransport):
    def __init__(self, public_url: str, internal_url: str):
        super().__init__()
        self.public = httpx2.URL(public_url)
        self.internal = httpx2.URL(internal_url)

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        public = request.url
        if (public.scheme, public.host, public.port) != (
            self.public.scheme,
            self.public.host,
            self.public.port,
        ):
            return await super().handle_async_request(request)
        # Keep the public Host header so Authentik generates browser-facing URLs.
        request.url = public.copy_with(
            scheme=self.internal.scheme,
            host=self.internal.host,
            port=self.internal.port,
        )
        try:
            return await super().handle_async_request(request)
        finally:
            request.url = public


class AuthentikClient(AsyncOAuth2Client):
    def __init__(self, *args, **kwargs):
        if settings.auth_internal_url:
            kwargs["transport"] = AuthentikTransport(settings.auth_url, settings.auth_internal_url)
        super().__init__(*args, **kwargs)


class AuthentikApp(StarletteOAuth2App):
    client_cls = AuthentikClient


oauth = OAuth()
oauth.register(
    "authentik",
    client_cls=AuthentikApp,
    client_id=settings.oidc_client_id,
    client_secret=settings.oidc_client_secret,
    server_metadata_url=f"{settings.oidc_issuer}.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},  # PKCE
)


def get_oidc() -> StarletteOAuth2App:
    return oauth.authentik


Oidc = Annotated[StarletteOAuth2App, Depends(get_oidc)]
