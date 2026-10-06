import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from shtab_core.db import Base


class Organization(Base):
    """Организация. Одна установка Shtab = одна организация, поэтому строка всегда одна."""

    __tablename__ = "organization"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    """Пользователь Shtab. Учётка и пароль — в Authentik; здесь профиль и роли в системе."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # sub из OIDC — постоянный id пользователя в Authentik
    oidc_sub: Mapped[str] = mapped_column(String(255), unique=True)
    username: Mapped[str] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(254))
    name: Mapped[str] = mapped_column(String(200))
    is_admin: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    # Доверенное лицо: может редактировать общие заметки организации
    is_trusted: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
