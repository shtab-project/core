import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from shtab_core.db import DbSession
from shtab_core.models import Organization, User
from shtab_core.schemas import Me, UserOut, UserUpdate
from shtab_core.users import AdminUser, CurrentUser, count_admins

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/me", response_model=Me, summary="Кто я")
async def me(user: CurrentUser, session: DbSession):
    return Me(user=user, organization=await session.get(Organization, 1))


@router.get("/users", response_model=list[UserOut], summary="Все пользователи (админ)")
async def list_users(_: AdminUser, session: DbSession):
    return (await session.scalars(select(User).order_by(User.created_at))).all()


@router.patch("/users/{user_id}", response_model=UserOut, summary="Роли пользователя (админ)")
async def update_user(user_id: uuid.UUID, body: UserUpdate, _: AdminUser, session: DbSession):
    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    if body.is_admin is False and target.is_admin and await count_admins(session) == 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "Нельзя снять последнего администратора")
    if body.is_admin is not None:
        target.is_admin = body.is_admin
    if body.is_trusted is not None:
        target.is_trusted = body.is_trusted
    await session.commit()
    return target
