from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.authenticate import get_current_user_claims
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db
from services import user_profiles
from services.schemas.user_profile import ExperienceTimeline, GeneralInfo

router = APIRouter(
    prefix="/v1/profile",
    tags=["profile"],
)


@router.get("", response_model=GeneralInfo)
async def get_profile(
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> GeneralInfo:
    return await user_profiles.get_general(db, claims.user_id)


@router.patch("", response_model=GeneralInfo)
async def update_profile(
    patch: GeneralInfo,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> GeneralInfo:
    return await user_profiles.update_general(db, claims.user_id, patch)


@router.get("/experience", response_model=ExperienceTimeline)
async def get_experience(
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> ExperienceTimeline:
    return await user_profiles.get_experience(db, claims.user_id)
