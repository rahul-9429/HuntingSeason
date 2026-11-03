from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.authenticate import get_current_user_claims
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db
from services import career_profiles
from services.schemas.career_profile import CareerProfile

router = APIRouter(
    prefix="/v1/career-profile",
    tags=["career-profile"],
)


@router.get("", response_model=Optional[CareerProfile])
async def get_career_profile(
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> Optional[CareerProfile]:
    return await career_profiles.get(db, claims.user_id)


@router.put("", response_model=CareerProfile)
async def put_career_profile(
    profile: CareerProfile,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> CareerProfile:
    return await career_profiles.upsert(db, claims.user_id, profile)
