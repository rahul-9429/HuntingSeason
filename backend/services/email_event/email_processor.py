import logging
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import AsyncSessionLocal
from models.contact import Contact
from models.email_event import EmailEvent
from models.enums import Direction
from models.mailbox import Mailbox
from models.sent_email import SentEmail
from models.user_contact import UserContact
from services.email_event import classification_worker, proposal_worker
from services.email_event.status_transition import (
    apply_sync_transition,
    is_automatic,
    is_mailer_daemon,
)
from services.email_event.threads import SNIPPET_CHARS
from services.email_event.types import NormalizedEmailMessage

logger = logging.getLogger(__name__)


async def _contact_already_in_thread(
    db: AsyncSession, mailbox_id: Optional[int], thread_id: str
) -> Optional[int]:
    return await db.scalar(
        select(EmailEvent.user_contact_id)
        .where(
            EmailEvent.mailbox_id == mailbox_id,
            EmailEvent.thread_id == thread_id,
            EmailEvent.user_contact_id.is_not(None),
        )
        .order_by(EmailEvent.sent_at.desc(), EmailEvent.id.desc())
        .limit(1)
    )


async def _contact_who_wrote(db: AsyncSession, user_id: int, from_address: str) -> Optional[int]:
    address = parseaddr(from_address)[1].strip().lower()
    if not address:
        return None
    return await db.scalar(
        select(UserContact.id)
        .join(Contact, Contact.id == UserContact.contact_id)
        .where(UserContact.user_id == user_id, func.lower(Contact.email) == address)
        .order_by(UserContact.id)
        .limit(1)
    )


class EventProcessingError(Exception):
    def __init__(self, failed: list[str]):
        super().__init__(f"{len(failed)} messages couldn't be processed")
        self.failed = failed


class EmailEventProcessor:
    async def process(self, mailbox: Mailbox, messages: Iterable[NormalizedEmailMessage]) -> int:
        new = 0
        failed: list[str] = []
        for message in messages:
            try:
                if await self._process_one(mailbox, message):
                    new += 1
            except Exception:
                logger.exception(
                    "Couldn't process message %s",
                    message.provider_message_id,
                    extra={"mailbox_id": mailbox.id, "provider_message_id": message.provider_message_id},
                )
                failed.append(message.provider_message_id)
        if failed:
            raise EventProcessingError(failed)
        return new

    async def _process_one(self, mailbox: Mailbox, message: NormalizedEmailMessage) -> bool:
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            anchor = await db.scalar(
                select(SentEmail)
                .where(SentEmail.mailbox_id == mailbox.id, SentEmail.thread_id == message.thread_id)
                .order_by(SentEmail.sent_at.desc(), SentEmail.id.desc())
                .limit(1)
            )
            user_contact_id = anchor.user_contact_id if anchor is not None else None
            if user_contact_id is None:
                user_contact_id = await _contact_already_in_thread(
                    db, mailbox.id, message.thread_id
                )
            if (
                user_contact_id is None
                and message.direction == Direction.INBOUND
                and not is_automatic(message.headers)
                and not is_mailer_daemon(message.from_address)
            ):
                user_contact_id = await _contact_who_wrote(
                    db, mailbox.user_id, message.from_address
                )
            if anchor is None and user_contact_id is None:
                return False

            event_id = await db.scalar(
                pg_insert(EmailEvent)
                .values(
                    user_id=mailbox.user_id,
                    mailbox_id=mailbox.id,
                    provider=message.provider,
                    provider_message_id=message.provider_message_id,
                    internet_message_id=message.internet_message_id,
                    thread_id=message.thread_id,
                    direction=message.direction,
                    from_address=message.from_address,
                    to_addresses=message.to_addresses,
                    cc_addresses=message.cc_addresses,
                    subject=message.subject,
                    snippet=message.snippet[:SNIPPET_CHARS],
                    body_html=message.body_html,
                    sent_at=message.sent_at,
                    sent_email_id=anchor.id if anchor is not None else None,
                    user_contact_id=user_contact_id,
                )
                .on_conflict_do_nothing(index_elements=["provider", "provider_message_id"])
                .returning(EmailEvent.id)
            )
            if event_id is None:
                return False

            await proposal_worker.expire_thread_proposals(db, mailbox.id, message.thread_id, now)
            await apply_sync_transition(
                db,
                user_contact_id=user_contact_id,
                direction=message.direction,
                from_address=message.from_address,
                sent_at=message.sent_at,
                now=now,
                automatic=is_automatic(message.headers),
            )
            await db.commit()

        logger.info(
            "New %s message in thread %s",
            message.direction.value,
            message.thread_id,
            extra={
                "mailbox_id": mailbox.id,
                "email_event_id": event_id,
                "direction": message.direction.value,
            },
        )
        if message.direction == Direction.INBOUND and user_contact_id is not None:
            try:
                await classification_worker.classify(event_id)
            except Exception:
                logger.exception(
                    "Couldn't classify email event %s",
                    event_id,
                    extra={"mailbox_id": mailbox.id, "email_event_id": event_id},
                )
        return True
