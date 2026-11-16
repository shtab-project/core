from collections.abc import Callable
from urllib.parse import urlsplit

from fastapi import FastAPI
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shtab_core.config import settings
from shtab_core.db import get_session_factory
from shtab_core.mcp_auth import ShtabTokenVerifier


class PluginTools:
    def __init__(self, server: MCPServer, app: FastAPI, plugin_id: str) -> None:
        self._server = server
        self._app = app
        self._plugin_id = plugin_id
        self._names: set[str] = set()

    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return session_factory(self._app)

    def tool(self, name: str, *, annotations: ToolAnnotations) -> Callable:
        full_name = f"{self._plugin_id}_{name}"

        def register(handler: Callable) -> Callable:
            if full_name in self._app.state.mcp_tool_names:
                raise ValueError(f"Инструмент MCP уже зарегистрирован: {full_name}")
            self._server.add_tool(handler, name=full_name, annotations=annotations)
            self._names.add(full_name)
            self._app.state.mcp_tool_names.add(full_name)
            return handler

        return register

    def close(self) -> None:
        for name in self._names:
            self._server.remove_tool(name)
            self._app.state.mcp_tool_names.remove(name)
        self._names.clear()


def session_factory(app: FastAPI) -> async_sessionmaker[AsyncSession]:
    provider = app.dependency_overrides.get(get_session_factory, get_session_factory)
    return provider()


def mount_mcp(app: FastAPI) -> None:
    public_url = settings.public_url.rstrip("/")
    public_host = urlsplit(public_url).netloc
    server = MCPServer(
        "Shtab",
        instructions="Работай с данными Shtab от имени владельца токена.",
        auth=AuthSettings(issuer_url=AnyHttpUrl(public_url), resource_server_url=None),
        token_verifier=ShtabTokenVerifier(lambda: session_factory(app)),
    )
    app.state.mcp = server
    app.state.mcp_tool_names = set()
    security = TransportSecuritySettings(
        allowed_hosts=[public_host, "localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"],
        allowed_origins=[public_url],
    )
    app.mount(
        "/mcp",
        server.streamable_http_app(
            streamable_http_path="/",
            stateless_http=True,
            json_response=True,
            transport_security=security,
        ),
    )
