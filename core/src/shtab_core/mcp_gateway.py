"""Mounts the Shtab MCP server and lets plugins register tools on it."""

from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from fastapi import FastAPI
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shtab_core.config import settings
from shtab_core.db import get_session_factory
from shtab_core.mcp_auth import MCPAuth, get_mcp_tokens
from shtab_core.uow import UnitOfWork

LOCAL_HOSTS = ("localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*")


def session_factory(app: FastAPI) -> async_sessionmaker[AsyncSession]:
    provider = app.dependency_overrides.get(get_session_factory, get_session_factory)
    return provider()


@dataclass
class PluginTools:
    """A plugin's handle for registering MCP tools under its own prefix."""

    server: MCPServer
    app: FastAPI
    plugin_id: str
    _names: set[str] = field(default_factory=set, init=False)

    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return session_factory(self.app)

    def tool(self, name: str, *, annotations: ToolAnnotations) -> Callable:
        full_name = f"{self.plugin_id}_{name}"

        def register(handler: Callable) -> Callable:
            if full_name in self.app.state.mcp_tool_names:
                raise ValueError(f"MCP tool is already registered: {full_name}")
            self.server.add_tool(handler, name=full_name, annotations=annotations)
            self._names.add(full_name)
            self.app.state.mcp_tool_names.add(full_name)
            return handler

        return register

    def close(self) -> None:
        for name in self._names:
            self.server.remove_tool(name)
            self.app.state.mcp_tool_names.remove(name)
        self._names.clear()


@dataclass
class AppTokenOwners:
    """Token owners from the store the app resolves now, so tests can override it."""

    app: FastAPI

    async def owner(self, value: str) -> UUID | None:
        provider = self.app.dependency_overrides.get(get_mcp_tokens, get_mcp_tokens)
        return await provider().owner(value)


@dataclass
class ActiveUsers:
    """`await active(user_id)`: the user still exists and is enabled."""

    app: FastAPI

    async def __call__(self, user_id: UUID) -> bool:
        async with UnitOfWork(session_factory(self.app)) as uow:
            user = await uow.users.get(user_id)
            return bool(user and user.is_active)


def mount_mcp(app: FastAPI) -> None:
    public_url = settings.public_url.rstrip("/")
    server = MCPServer(
        "Shtab",
        instructions="Work with Shtab data on behalf of the token owner.",
        auth=AuthSettings(issuer_url=AnyHttpUrl(public_url), resource_server_url=None),
        token_verifier=MCPAuth(storage=AppTokenOwners(app), is_active=ActiveUsers(app)),
    )
    app.state.mcp = server
    app.state.mcp_tool_names = set()
    security = TransportSecuritySettings(
        allowed_hosts=[*settings.mcp_hosts, *LOCAL_HOSTS],
        allowed_origins=settings.mcp_origins,
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
