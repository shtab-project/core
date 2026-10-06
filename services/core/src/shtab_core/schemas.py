import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    name: str
    email: str | None
    is_admin: bool
    is_trusted: bool
    created_at: datetime
    last_login_at: datetime | None


class UserUpdate(BaseModel):
    is_admin: bool | None = None
    is_trusted: bool | None = None


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
    # Куда отправить браузер, чтобы завершить сессию и в Authentik
    logout_url: str | None
