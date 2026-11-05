import logging
import os
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.daily_send_usage import DailySendUsage

logger = logging.getLogger(__name__)

DAILY_SEND_CAP = int(os.getenv("DAILY_SEND_CAP", "20"))

_WARMUP_RAMP = ((3, 15), (7, 25), (14, 40))


def warmup_days(warmup_started_at: datetime, now: datetime) -> int:
    return max(0, (now - warmup_started_at).days)


def daily_cap(warmup_started_at: datetime, now: datetime) -> int:
    days = warmup_days(warmup_started_at, now)
    for below, cap in _WARMUP_RAMP:
        if days < below:
            return min(cap, DAILY_SEND_CAP)
    return DAILY_SEND_CAP


def follow_up_share(cap: int) -> int:
    return cap // 5


def _today() -> date:
    return datetime.now(timezone.utc).date()


async def _reserve(
    db: AsyncSession, user_id: int, allowed: Any, *, follow_up: bool
) -> Optional[date]:
    today = _today()
    await db.execute(
        pg_insert(DailySendUsage)
        .values(user_id=user_id, usage_date=today)
        .on_conflict_do_nothing(index_elements=["user_id", "usage_date"])
    )
    values: dict[str, Any] = {"sends": DailySendUsage.sends + 1}
    if follow_up:
        values["follow_up_sends"] = DailySendUsage.follow_up_sends + 1
    reserved = await db.scalar(
        update(DailySendUsage)
        .where(DailySendUsage.user_id == user_id, DailySendUsage.usage_date == today, allowed)
        .values(**values)
        .returning(DailySendUsage.sends)
    )
    await db.commit()
    return today if reserved is not None else None


async def reserve_first_touch(
    db: AsyncSession, user_id: int, cap: int, follow_ups_due: bool
) -> Optional[date]:
    if follow_ups_due:
        unused_share = func.greatest(0, follow_up_share(cap) - DailySendUsage.follow_up_sends)
        allowed = DailySendUsage.sends < cap - unused_share
    else:
        allowed = DailySendUsage.sends < cap
    return await _reserve(db, user_id, allowed, follow_up=False)


async def reserve_follow_up(
    db: AsyncSession, user_id: int, cap: int, new_leads_waiting: bool
) -> Optional[date]:
    if new_leads_waiting:
        allowed = and_(
            DailySendUsage.follow_up_sends < follow_up_share(cap), DailySendUsage.sends < cap
        )
    else:
        allowed = DailySendUsage.sends < (cap * 4) // 5
    return await _reserve(db, user_id, allowed, follow_up=True)


async def reserve_reply(db: AsyncSession, user_id: int, cap: int) -> Optional[date]:
    return await _reserve(db, user_id, DailySendUsage.sends < cap, follow_up=False)


async def release(db: AsyncSession, user_id: int, day: date, *, follow_up: bool = False) -> None:
    values: dict[str, Any] = {"sends": func.greatest(0, DailySendUsage.sends - 1)}
    if follow_up:
        values["follow_up_sends"] = func.greatest(0, DailySendUsage.follow_up_sends - 1)
    await db.execute(
        update(DailySendUsage)
        .where(DailySendUsage.user_id == user_id, DailySendUsage.usage_date == day)
        .values(**values)
    )
    await db.commit()


async def sends_today(db: AsyncSession, user_id: int) -> int:
    sends = await db.scalar(
        select(DailySendUsage.sends).where(
            DailySendUsage.user_id == user_id, DailySendUsage.usage_date == _today()
        )
    )
    return sends or 0
