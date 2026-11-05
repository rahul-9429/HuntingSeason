import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from db.session import AsyncSessionLocal
from models.email_event import EmailEvent
from models.enums import Direction
from services.email_event import classification_worker

logger = logging.getLogger(__name__)

RETRY_AFTER = timedelta(minutes=5)
GIVE_UP_AFTER = timedelta(days=3)
BATCH_SIZE = 50


async def handle(payload: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        event_ids = (
            await db.scalars(
                select(EmailEvent.id)
                .where(
                    EmailEvent.direction == Direction.INBOUND,
                    EmailEvent.user_contact_id.is_not(None),
                    EmailEvent.classified_at.is_(None),
                    EmailEvent.created_at <= now - RETRY_AFTER,
                    EmailEvent.created_at > now - GIVE_UP_AFTER,
                )
                .order_by(EmailEvent.id)
                .limit(BATCH_SIZE)
            )
        ).all()
    for event_id in event_ids:
        try:
            await classification_worker.classify(event_id)
        except Exception:
            logger.exception(
                "Couldn't classify email event %s", event_id, extra={"email_event_id": event_id}
            )
