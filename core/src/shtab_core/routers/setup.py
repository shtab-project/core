"""First-run wizard: name the organization; the first user becomes admin."""

from fastapi import APIRouter, status

from shtab_core.dependencies import CurrentUser, Setup
from shtab_core.schemas import OrganizationOut, SetupIn, SetupStatus

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("", response_model=SetupStatus, summary="Is Shtab set up")
async def get_status(service: Setup):
    org = await service.get_organization()
    return SetupStatus(
        initialized=bool(org),
        organization=OrganizationOut.model_validate(org) if org else None,
    )


@router.post(
    "",
    response_model=OrganizationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Initial setup: create the organization and become admin",
)
async def run_setup(body: SetupIn, user: CurrentUser, service: Setup):
    return await service.setup(body.organization_name, user)
