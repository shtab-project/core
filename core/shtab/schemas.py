import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from shtab.models import Scope, Status


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scope: Scope
    path: str
    title: str
    status: Status
    done: bool
    due: date | None
    tags: list[str]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    scope: Scope = Scope.personal
    due: date | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)


class StatusUpdate(BaseModel):
    status: Status


class Board(BaseModel):
    """Канбан: колонки в порядке статусов."""

    columns: dict[Status, list[TaskOut]]
