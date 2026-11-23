import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from shtab_core.constants import (
    PLUGIN_ENTRYPOINT_MAX_LENGTH,
    PLUGIN_ID_MAX_LENGTH,
    PLUGIN_NAME_MAX_LENGTH,
    PLUGIN_URL_MAX_LENGTH,
    PLUGIN_VERSION_MAX_LENGTH,
)
from shtab_core.manifest import Plugin, PluginFrontend


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    name: str
    email: str | None
    is_admin: bool
    is_trusted: bool
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class UserUpdate(BaseModel):
    is_admin: bool | None = None
    is_trusted: bool | None = None
    is_active: bool | None = None


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    created_at: datetime


class SetupStatus(BaseModel):
    initialized: bool
    organization: OrganizationOut | None


class SetupIn(BaseModel):
    organization_name: str = Field(min_length=1, max_length=200)


class Me(BaseModel):
    user: UserOut
    organization: OrganizationOut | None


class LogoutOut(BaseModel):
    # Where to send the browser to end the Authentik session too
    logout_url: str | None


class PluginIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=PLUGIN_ID_MAX_LENGTH)
    name: str = Field(min_length=1, max_length=PLUGIN_NAME_MAX_LENGTH)
    version: str = Field(min_length=1, max_length=PLUGIN_VERSION_MAX_LENGTH)
    url: str = Field(min_length=1, max_length=PLUGIN_URL_MAX_LENGTH)
    backend_entrypoint: str = Field(
        min_length=1, max_length=PLUGIN_ENTRYPOINT_MAX_LENGTH
    )
    mcp_entrypoint: str | None = Field(
        default=None, min_length=1, max_length=PLUGIN_ENTRYPOINT_MAX_LENGTH
    )
    frontend: PluginFrontend | None = None

    def to_plugin(self) -> Plugin:
        return Plugin(
            id=self.id,
            name=self.name,
            version=self.version,
            url=self.url,
            backend_entrypoint=self.backend_entrypoint,
            mcp_entrypoint=self.mcp_entrypoint,
            frontend=self.frontend,
        )


class McpTokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    expires_in: int


class McpTokenIssued(BaseModel):
    id: str
    token: str
    expires_in: int


class CatalogPluginOut(BaseModel):
    id: str
    name: str
    version: str
    description: str
    icon: str
    installed_version: str | None


class PluginOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    version: str
    url: str
    backend_entrypoint: str
    frontend: PluginFrontend | None
