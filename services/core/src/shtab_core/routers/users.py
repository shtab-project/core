import uuid

from fastapi import APIRouter

from shtab_core.dependencies import AdminUser, CurrentUser, Users
from shtab_core.schemas import Me, OrganizationOut, UserOut, UserUpdate

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/me", response_model=Me, summary="Кто я")
async def me(user: CurrentUser, users: Users):
    organization = await users.get_organization()
    return Me(
        user=UserOut.model_validate(user),
        organization=OrganizationOut.model_validate(organization) if organization else None,
    )


@router.get("/users", response_model=list[UserOut], summary="Все пользователи (админ)")
async def list_users(_: AdminUser, users: Users):
    return await users.list()


@router.patch("/users/{user_id}", response_model=UserOut, summary="Роли пользователя (админ)")
async def update_user(user_id: uuid.UUID, body: UserUpdate, _: AdminUser, users: Users):
    return await users.update_roles(user_id, is_admin=body.is_admin, is_trusted=body.is_trusted)
