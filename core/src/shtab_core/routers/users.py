import uuid

from fastapi import APIRouter

from shtab_core.dependencies import AdminUser, CurrentUser, Users
from shtab_core.mcp_auth import McpTokens
from shtab_core.schemas import Me, OrganizationOut, UserOut, UserUpdate
from shtab_core.sessions import Sessions

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/me", response_model=Me, summary="Current user")
async def me(user: CurrentUser, users: Users):
    organization = await users.get_organization()
    return Me(
        user=UserOut.model_validate(user),
        organization=OrganizationOut.model_validate(organization)
        if organization
        else None,
    )


@router.get("/users", response_model=list[UserOut], summary="All users (admin)")
async def list_users(_: AdminUser, users: Users):
    return await users.list()


@router.patch(
    "/users/{user_id}",
    response_model=UserOut,
    summary="User roles and access (admin)",
    description="`is_active: false` disables the account: login is blocked "
    "and all of the user's sessions and MCP tokens are revoked.",
)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    admin: AdminUser,
    users: Users,
    sessions: Sessions,
    tokens: McpTokens,
):
    user = await users.update_roles(
        user_id,
        is_admin=body.is_admin,
        is_trusted=body.is_trusted,
        is_active=body.is_active,
        actor_id=admin.id,
    )
    if not user.is_active:
        await sessions.revoke_user(user.id)
        await tokens.revoke_user(user.id)
    return user
