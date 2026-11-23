import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self

from shtab_core.exceptions import ForbiddenError, InvalidInputError, UnauthorizedError
from shtab_core.models import User
from shtab_core.uow import UnitOfWork


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


@dataclass(frozen=True)
class OidcClaims:
    """User profile from Authentik userinfo."""

    sub: str
    username: str
    name: str
    email: str | None = None

    @classmethod
    def from_userinfo(cls, userinfo: Mapping[str, object]) -> Self:
        sub = _text(userinfo.get("sub"))
        if not sub:
            raise InvalidInputError("Authentik response has no sub")
        username = _text(userinfo.get("preferred_username")) or sub
        email = userinfo.get("email")
        return cls(
            sub=sub,
            username=username,
            name=_text(userinfo.get("name")) or username,
            email=email if isinstance(email, str) else None,
        )


@dataclass
class AuthService:
    uow: UnitOfWork

    async def upsert_from_claims(self, claims: OidcClaims) -> User:
        async with self.uow.transaction():
            user = await self.uow.users.get_by_oidc_sub(claims.sub)
            if not user:
                user = await self.uow.users.create(claims.sub)
            elif not user.is_active:
                raise ForbiddenError("Account disabled by an admin")
            await self.uow.users.update_profile(
                user,
                username=claims.username,
                name=claims.name,
                email=claims.email,
                last_login_at=datetime.now(UTC),
            )

        return user

    async def current_user(self, user_id: uuid.UUID | None) -> User:
        user = await self.uow.users.get(user_id) if user_id else None
        if not user or not user.is_active:
            raise UnauthorizedError("Login required")
        return user
