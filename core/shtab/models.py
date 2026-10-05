import enum
import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shtab.db import Base


class Scope(enum.StrEnum):
    personal = "personal"
    shared = "shared"


class Status(enum.StrEnum):
    todo = "todo"
    doing = "doing"
    review = "review"
    done = "done"


def _str_enum(cls: type[enum.StrEnum]) -> Enum:
    return Enum(cls, native_enum=False, length=16, values_callable=lambda e: [m.value for m in e])


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Task(Base):
    """Индекс задачи из markdown-файла.

    Источник истины — файл в пространстве заметок; строка таблицы пересобирается
    индексатором, но id сохраняется, пока задача узнаваема (см. notes.indexer).
    """

    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_space", "scope", "owner_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope: Mapped[Scope] = mapped_column(_str_enum(Scope))
    # NULL для общих задач
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String(1024))  # относительно корня пространства
    line: Mapped[int]
    raw: Mapped[str] = mapped_column(Text)  # исходная строка — для безопасной записи обратно
    title: Mapped[str] = mapped_column(Text)
    done: Mapped[bool]
    status: Mapped[Status] = mapped_column(_str_enum(Status))
    due: Mapped[date | None]
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
