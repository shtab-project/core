"""Мастер первого запуска: название организации, первый прошедший — администратор."""

from fastapi import APIRouter, status

from shtab_core.dependencies import CurrentUser, Setup
from shtab_core.schemas import OrganizationOut, SetupIn, SetupStatus

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("", response_model=SetupStatus, summary="Настроен ли Shtab")
async def get_status(service: Setup):
    org = await service.get_organization()
    return SetupStatus(
        initialized=org is not None,
        organization=OrganizationOut.model_validate(org) if org else None,
    )


@router.post(
    "",
    response_model=OrganizationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Первичная настройка: создать организацию и стать администратором",
)
async def run_setup(body: SetupIn, user: CurrentUser, service: Setup):
    return await service.setup(body.organization_name, user)
