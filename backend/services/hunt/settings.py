from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.hunt_settings import HuntSettings


async def get_settings(db: AsyncSession, user_id: int) -> HuntSettings:
    settings = await db.get(HuntSettings, user_id)
    if settings is None:
        await db.execute(
            pg_insert(HuntSettings)
            .values(user_id=user_id)
            .on_conflict_do_nothing(index_elements=["user_id"])
        )
        await db.commit()
        settings = await db.get(HuntSettings, user_id)
        if settings is None:
            raise RuntimeError(f"Couldn't create hunt settings for user {user_id}")
    return settings
