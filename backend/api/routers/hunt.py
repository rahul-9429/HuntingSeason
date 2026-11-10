from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services import hunt_settings
from api.api_services.errors import ServiceError
from api.dependencies.authenticate import get_current_user_claims
from api.type_models.hunt import HuntQueued, HuntSettingsOut, HuntSettingsUpdate
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db

router = APIRouter(
    prefix="/v1/hunt",
    tags=["hunt"],
)


@router.get("/settings", response_model=HuntSettingsOut)
async def get_settings(
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> HuntSettingsOut:
    try:
        return await hunt_settings.read(db, claims.user_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.put("/settings", response_model=HuntSettingsOut)
async def update_settings(
    req: HuntSettingsUpdate,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> HuntSettingsOut:
    try:
        return await hunt_settings.update(db, claims.user_id, req)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/run", response_model=HuntQueued, status_code=202)
async def run_now(
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> HuntQueued:
    await hunt_settings.queue_run(db, claims.user_id)
    return HuntQueued(queued=True)
