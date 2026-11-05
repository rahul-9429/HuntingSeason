import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable

from sqlalchemy import and_, or_, select

from db.session import AsyncSessionLocal
from models.enums import MailboxProvider, MailboxStatus
from models.hunt_settings import HuntSettings
from models.mailbox import Mailbox
from models.outreach_settings import OutreachSettings
from models.user import User
from services import mailbox_manager
from services.hunt import auto_hunt
from services.redis import get_redis, key, push_task, webhooks

logger = logging.getLogger(__name__)

TICK_SECONDS = 30
MINUTE = 60
HOUR = 60 * MINUTE


@dataclass(frozen=True)
class Job:
    name: str
    interval_seconds: int
    run: Callable[[], Awaitable[None]]


def _enqueue(task: str) -> Callable[[], Awaitable[None]]:
    async def run() -> None:
        await push_task(task, {})

    return run


async def _safety_sync() -> None:
    for mailbox in await mailbox_manager.active():
        if mailbox.provider == MailboxProvider.GMAIL:
            if await webhooks.claim_gmail_sync(mailbox.id):
                await push_task("gmail_sync", {"mailbox_id": mailbox.id, "batch": False})
        else:
            await push_task("outlook_safety_sync", {"mailbox_id": mailbox.id})


async def _outreach() -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        user_ids = (
            await db.scalars(
                select(OutreachSettings.user_id)
                .join(Mailbox, Mailbox.user_id == OutreachSettings.user_id)
                .where(
                    OutreachSettings.enabled.is_(True),
                    Mailbox.status == MailboxStatus.ACTIVE,
                    or_(Mailbox.next_send_at.is_(None), Mailbox.next_send_at <= now),
                )
            )
        ).all()
    for user_id in user_ids:
        await push_task("outreach_run", {"user_id": user_id, "scheduled": True})


async def _auto_hunt() -> None:
    async with AsyncSessionLocal() as db:
        user_ids = (
            await db.scalars(
                select(User.id)
                .outerjoin(HuntSettings, HuntSettings.user_id == User.id)
                .where(
                    or_(
                        HuntSettings.user_id.is_(None),
                        and_(HuntSettings.enabled.is_(True), auto_hunt.is_due()),
                    )
                )
            )
        ).all()
    for user_id in user_ids:
        await push_task("auto_hunt", {"user_id": user_id, "scheduled": True})


JOBS: list[Job] = [
    Job("gmail_watch_renew", 6 * HOUR, _enqueue("gmail_watch_renew")),
    Job("outlook_subscription_renew", 6 * HOUR, _enqueue("outlook_subscription_renew")),
    Job("mailbox_safety_sync", 15 * MINUTE, _safety_sync),
    Job("outreach_run", 2 * MINUTE, _outreach),
    Job("auto_hunt", HOUR, _auto_hunt),
    Job("proposal_auto_send", MINUTE, _enqueue("proposal_auto_send")),
    Job("proposal_expire", HOUR, _enqueue("proposal_expire")),
    Job("classify_pending", 10 * MINUTE, _enqueue("classify_pending")),
]


async def tick() -> None:
    redis = get_redis()
    for job in JOBS:
        job_key = key("scheduler", job.name)
        try:
            if await redis.set(job_key, "1", nx=True, ex=job.interval_seconds):
                logger.info("Running scheduled job %s", job.name, extra={"job": job.name})
                await job.run()
        except Exception:
            logger.exception("Scheduled job %s failed", job.name, extra={"job": job.name})
            try:
                await redis.delete(job_key)
            except Exception:
                logger.exception("Couldn't reset scheduled job %s", job.name)


async def run_forever() -> None:
    while True:
        await tick()
        await asyncio.sleep(TICK_SECONDS)
