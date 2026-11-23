from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from shtab_core.db import Base


class Organization(Base):
    """The organization; one per Shtab installation."""

    __tablename__ = "organization"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PluginRecord(Base):
    """A registered plugin; its code lives on disk."""

    __tablename__ = "plugins"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(2048))
    backend_entrypoint: Mapped[str] = mapped_column(String(500))
    frontend: Mapped[dict[str, object] | None] = mapped_column(JSON(none_as_null=True))


class User(Base):
    """User profile and roles; the account and password live in Authentik."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    # OIDC sub: the user's permanent Authentik id
    oidc_sub: Mapped[str] = mapped_column(String(255), unique=True)
    username: Mapped[str] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(254))
    name: Mapped[str] = mapped_column(String(200))
    is_admin: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    # Trusted users can edit the organization's shared notes
    is_trusted: Mapped[bool] = mapped_column(
        default=False, server_default=text("false")
    )
    # Disabled users can't log in; their sessions and MCP tokens are revoked
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    projects: Mapped[list[Project]] = relationship(
        secondary="users_projects",
        back_populates="users",
        lazy="raise",
        passive_deletes=True,
    )


class Project(Base):
    """A project the admin adds members to."""

    __tablename__ = "projects"
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(200), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    users: Mapped[list[User]] = relationship(
        secondary="users_projects",
        back_populates="projects",
        lazy="raise",
        passive_deletes=True,
    )


class UsersXProjects(Base):
    """Project membership; one row per user–project pair."""

    __tablename__ = "users_projects"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "project_id", name="uq_users_projects_user_project"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
