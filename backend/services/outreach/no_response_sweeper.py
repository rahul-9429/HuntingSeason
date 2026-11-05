import logging
from datetime import datetime, timedelta

from sqlalchemy import update

from db.session import AsyncSessionLocal
from models.enums import OutreachStage
from models.outreach_settings import OutreachSettings
from models.user_contact import UserContact

logger = logging.getLogger(__name__)


async def sweep(user_id: int, settings: OutreachSettings, now: datetime) -> int:
    async with AsyncSessionLocal() as db:
        moved = (
            await db.execute(
                update(UserContact)
                .where(
                    UserContact.user_id == user_id,
                    UserContact.stage == OutreachStage.CONTACTED,
                    UserContact.follow_up_count >= settings.max_follow_ups,
                    UserContact.last_contacted_at
                    <= now - timedelta(days=settings.follow_up_interval_days),
                    UserContact.replied_at.is_(None),
                )
                .values(stage=OutreachStage.DEAD, stage_changed_at=now)
                .returning(UserContact.id)
            )
        ).scalars().all()
        await db.commit()
    if moved:
        logger.info(
            "%d contacts of user %s got no response",
            len(moved),
            user_id,
            extra={"user_id": user_id, "count": len(moved)},
        )
    return len(moved)
