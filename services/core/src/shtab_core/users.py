from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shtab_core.db import DbSession
from shtab_core.models import User
from shtab_core.sessions import COOKIE, Sessions


async def upsert_from_claims(session: AsyncSession, claims: dict) -> User:
    """Создать или обновить пользователя по данным из ID-токена Authentik."""
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "В ответе Authentik нет sub")
    user = await session.scalar(select(User).where(User.oidc_sub == sub))
    if user is None:
        user = User(oidc_sub=sub)
        session.add(user)
    user.username = claims.get("preferred_username") or sub
    user.name = claims.get("name") or user.username
    user.email = claims.get("email")
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    return user


async def count_admins(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(User).where(User.is_admin))


async def current_user(request: Request, session: DbSession, sessions: Sessions) -> User:
    session_id = request.cookies.get(COOKIE)
    user_id = await sessions.get(session_id) if session_id else None
    user = await session.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Нужно войти")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Только для администратора")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
