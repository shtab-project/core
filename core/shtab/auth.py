from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shtab.config import settings
from shtab.db import get_session
from shtab.models import User
from shtab.notes.spaces import USERNAME_RE
from shtab.tasks import get_or_create_user


async def current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    x_authentik_username: Annotated[str | None, Header()] = None,
) -> User:
    """Пользователь запроса.

    В проде ядро доступно только через Traefik + Authentik forward-auth: Authentik
    проверяет вход и сам выставляет X-Authentik-Username (подделать снаружи нельзя,
    Traefik перезаписывает заголовок). Без Authentik — dev-режим с одним пользователем.
    """
    username = x_authentik_username or (settings.dev_user if settings.dev_mode else None)
    if not username or not USERNAME_RE.match(username):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Нужен вход через Shtab")
    return await get_or_create_user(session, username)


CurrentUser = Annotated[User, Depends(current_user)]
DbSession = Annotated[AsyncSession, Depends(get_session)]
