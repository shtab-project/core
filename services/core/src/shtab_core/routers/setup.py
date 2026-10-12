"""Мастер первого запуска: название организации, первый прошедший — администратор."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from shtab_core.db import DbSession
from shtab_core.models import Organization
from shtab_core.schemas import OrganizationOut, SetupIn, SetupStatus
from shtab_core.users import CurrentUser

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("", response_model=SetupStatus, summary="Настроен ли Shtab")
async def get_status(session: DbSession):
    org = await session.get(Organization, 1)
    return SetupStatus(initialized=org is not None, organization=org) # 


@router.post(
    "",
    response_model=OrganizationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Первичная настройка: создать организацию и стать администратором",
)
async def run_setup(body: SetupIn, session: DbSession, user: CurrentUser):
    if await session.get(Organization, 1):
        raise HTTPException(status.HTTP_409_CONFLICT, "Shtab уже настроен")
    org = Organization(id=1, name=body.organization_name.strip())
    session.add(org)
    user.is_admin = True
    user.is_trusted = True
    try:
        await session.commit()
    except IntegrityError:  # два человека одновременно — второй проиграл
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Shtab уже настроен") from None
    return org
