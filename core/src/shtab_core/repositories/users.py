from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shtab_core.models import User


@dataclass
class UserRepository:
    """Users. The caller ends the transaction."""

    session: AsyncSession

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_oidc_sub(self, oidc_sub: str) -> User | None:
        query = select(User).where(User.oidc_sub == oidc_sub)
        return await self.session.scalar(query)

    async def list(self) -> list[User]:
        query = select(User).order_by(User.created_at, User.id)
        users = await self.session.scalars(query)
        return list(users)

    async def create(self, oidc_sub: str) -> User:
        user = User(oidc_sub=oidc_sub)
        self.session.add(user)
        return user

    async def update_profile(
        self,
        user: User,
        *,
        username: str,
        name: str,
        email: str | None,
        last_login_at: datetime,
    ) -> User:
        user.username = username
        user.name = name
        user.email = email
        user.last_login_at = last_login_at
        return user

    async def count_admins(self) -> int:
        admin_count = await self.session.scalar(
            select(func.count()).select_from(User).where(User.is_admin, User.is_active)
        )
        return admin_count or 0

    async def update_roles(
        self,
        user: User,
        *,
        is_admin: bool | None = None,
        is_trusted: bool | None = None,
        is_active: bool | None = None,
    ) -> User:
        if is_active is not None:
            user.is_active = is_active
        if is_admin is not None:
            user.is_admin = is_admin
        if is_trusted is not None:
            user.is_trusted = is_trusted
        return user
