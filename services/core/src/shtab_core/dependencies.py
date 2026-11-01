from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shtab_core.constants import COOKIE
from shtab_core.db import get_session_factory
from shtab_core.models import User
from shtab_core.services.auth import AuthService
from shtab_core.services.projects import ProjectService
from shtab_core.services.setup import SetupService
from shtab_core.services.users import UserService
from shtab_core.sessions import Sessions
from shtab_core.uow import UnitOfWork


async def get_uow(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AsyncIterator[UnitOfWork]:
    async with UnitOfWork(session_factory) as uow:
        yield uow


Uow = Annotated[UnitOfWork, Depends(get_uow)]


def get_auth_service(uow: Uow) -> AuthService:
    return AuthService(uow)


Auth = Annotated[AuthService, Depends(get_auth_service)]


def get_setup_service(uow: Uow) -> SetupService:
    return SetupService(uow)


Setup = Annotated[SetupService, Depends(get_setup_service)]


def get_user_service(uow: Uow) -> UserService:
    return UserService(uow)


Users = Annotated[UserService, Depends(get_user_service)]


def get_project_service(uow: Uow) -> ProjectService:
    return ProjectService(uow)


Projects = Annotated[ProjectService, Depends(get_project_service)]


async def current_user(request: Request, auth: Auth, sessions: Sessions) -> User:
    session_id = request.cookies.get(COOKIE)
    user_id = await sessions.get(session_id) if session_id else None
    return await auth.current_user(user_id)


CurrentUser = Annotated[User, Depends(current_user)]


async def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Только для администратора")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
