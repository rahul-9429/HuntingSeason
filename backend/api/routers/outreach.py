from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services import outreach, outreach_settings
from api.api_services.errors import ServiceError
from api.dependencies.authenticate import get_current_user_claims
from api.type_models.outreach import AddToOutreachRequest, OutreachCompany
from api.type_models.outreach_settings import (
    EmailSendScheduleOut,
    EmailSendScheduleUpdate,
    OutreachSettingsOut,
    OutreachSettingsUpdate,
    PreviewOut,
    PreviewRequest,
    RunQueued,
)
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db
from services.hunt import contact_finder

router = APIRouter(
    prefix="/v1/outreach",
    tags=["outreach"],
)


@router.post("/companies", response_model=OutreachCompany, status_code=202)
async def add_company(
    req: AddToOutreachRequest,
    background_tasks: BackgroundTasks,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> OutreachCompany:
    try:
        company, search_id = await outreach.add(db, claims.user_id, req)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    if search_id is not None:
        background_tasks.add_task(contact_finder.find_contacts, search_id)
    return company


@router.get("/companies", response_model=list[OutreachCompany])
async def list_companies(
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> list[OutreachCompany]:
    return await outreach.list_for(db, claims.user_id)


@router.delete("/companies/{org_id}", status_code=204)
async def remove_company(
    org_id: str = Path(pattern=r"^[0-9a-f]{24}$"),
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    await outreach.remove(db, claims.user_id, org_id)
    return Response(status_code=204)


@router.get("/settings", response_model=OutreachSettingsOut)
async def get_settings(
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> OutreachSettingsOut:
    return await outreach_settings.read(db, claims.user_id)


@router.put("/settings", response_model=OutreachSettingsOut)
async def update_settings(
    req: OutreachSettingsUpdate,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> OutreachSettingsOut:
    return await outreach_settings.update(db, claims.user_id, req)


@router.get("/settings/email-send-schedule", response_model=EmailSendScheduleOut)
async def get_email_send_schedule(
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> EmailSendScheduleOut:
    return await outreach_settings.read_send_schedule(db, claims.user_id)


@router.patch("/settings/email-send-schedule", response_model=EmailSendScheduleOut)
async def update_email_send_schedule(
    req: EmailSendScheduleUpdate,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> EmailSendScheduleOut:
    try:
        return await outreach_settings.update_send_schedule(db, claims.user_id, req)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/run", response_model=RunQueued, status_code=202)
async def run_now(claims: UserClaims = Depends(get_current_user_claims)) -> RunQueued:
    await outreach_settings.queue_run(claims.user_id)
    return RunQueued(queued=True)


@router.post("/preview", response_model=PreviewOut)
async def preview(
    req: PreviewRequest,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> PreviewOut:
    try:
        return await outreach_settings.preview(db, claims.user_id, req)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
