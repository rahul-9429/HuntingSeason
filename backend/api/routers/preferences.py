from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.authenticate import get_current_user_claims
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db
from services import user_profiles
from services.schemas.user_profile import Preferences

router = APIRouter(
    prefix="/v1/preferences",
    tags=["preferences"],
)


@router.get("", response_model=Preferences, response_model_exclude_none=True)
async def get_preferences(
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> Preferences:
    return await user_profiles.get_preferences(db, claims.user_id)


@router.patch("", response_model=Preferences, response_model_exclude_none=True)
async def update_preferences(
    patch: Preferences,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> Preferences:
    return await user_profiles.update_preferences(db, claims.user_id, patch)
