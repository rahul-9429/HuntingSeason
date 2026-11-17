import random
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from sqlalchemy import update

from db.session import AsyncSessionLocal
from models.mailbox import Mailbox
from models.outreach_settings import OutreachSettings


def next_gap(settings: OutreachSettings) -> timedelta:
    low = max(1, settings.min_gap_seconds)
    high = max(low, settings.max_gap_seconds)
    return timedelta(seconds=random.randint(low, high))


def is_due(next_send_at: Optional[datetime], now: datetime) -> bool:
    return next_send_at is None or next_send_at <= now


def next_utc_day(now: datetime) -> datetime:
    tomorrow = now.astimezone(timezone.utc).date() + timedelta(days=1)
    return datetime.combine(tomorrow, time.min, tzinfo=timezone.utc)


async def hold_until(mailbox_id: int, when: datetime) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Mailbox).where(Mailbox.id == mailbox_id).values(next_send_at=when)
        )
        await db.commit()


async def hold_for_gap(mailbox_id: int, settings: OutreachSettings, now: datetime) -> None:
    await hold_until(mailbox_id, now + next_gap(settings))
