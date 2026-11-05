from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import DeliveryStatus
from models.sent_email import SentEmail

WINDOW = timedelta(days=7)


async def bounce_counts(db: AsyncSession, mailbox_id: int, now: datetime) -> tuple[int, int]:
    bounced = func.count().filter(
        SentEmail.delivery_status.in_([DeliveryStatus.BOUNCED_SOFT, DeliveryStatus.BOUNCED_HARD])
    )
    row = (
        await db.execute(
            select(func.count(), bounced).where(
                SentEmail.mailbox_id == mailbox_id, SentEmail.sent_at >= now - WINDOW
            )
        )
    ).one()
    return int(row[0]), int(row[1])


async def bounce_rate(db: AsyncSession, mailbox_id: int, now: datetime) -> Optional[float]:
    sends, bounces = await bounce_counts(db, mailbox_id, now)
    return bounces / sends if sends else None
