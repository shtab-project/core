import uuid
from collections.abc import Mapping
from datetime import UTC, datetime

from shtab_core.models import User
from shtab_core.services.errors import InvalidInputError, UnauthorizedError
from shtab_core.uow import UnitOfWork


class AuthService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def upsert_from_claims(self, claims: Mapping[str, object]) -> User:
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub:
            raise InvalidInputError("В ответе Authentik нет sub")
        user = await self.uow.users.get_by_oidc_sub(sub)
        if user is None:
            user = await self.uow.users.create(sub)
        username = claims.get("preferred_username")
        name = claims.get("name")
        email = claims.get("email")
        username = username if isinstance(username, str) and username else sub
        await self.uow.users.update_profile(
            user,
            username=username,
            name=name if isinstance(name, str) and name else username,
            email=email if isinstance(email, str) else None,
            last_login_at=datetime.now(UTC),
        )
        await self.uow.commit()
        return user

    async def current_user(self, user_id: uuid.UUID | None) -> User:
        user = await self.uow.users.get(user_id) if user_id else None
        if user is None:
            raise UnauthorizedError("Нужно войти")
        return user
