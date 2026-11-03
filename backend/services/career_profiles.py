import logging
from typing import Any, Optional

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.career_profile import CareerProfile as CareerProfileRow
from services.schemas.career_profile import CareerProfile

logger = logging.getLogger(__name__)


async def get(db: AsyncSession, user_id: int) -> Optional[CareerProfile]:
    data = (
        await db.execute(select(CareerProfileRow.data).where(CareerProfileRow.user_id == user_id))
    ).scalar_one_or_none()
    if data is None:
        return None
    try:
        return CareerProfile.model_validate(data)
    except ValidationError:
        logger.warning("Ignoring an unreadable career profile for user %s", user_id)
        return None


async def upsert(
    db: AsyncSession,
    user_id: int,
    profile: CareerProfile,
    source_resume_id: Optional[int] = None,
) -> CareerProfile:
    values: dict[str, Any] = {"data": profile.model_dump(), "updated_at": func.now()}
    if source_resume_id is not None:
        values["source_resume_id"] = source_resume_id
    insert = pg_insert(CareerProfileRow).values(user_id=user_id, **values)
    await db.execute(insert.on_conflict_do_update(index_elements=["user_id"], set_=values))
    await db.commit()
    return profile
