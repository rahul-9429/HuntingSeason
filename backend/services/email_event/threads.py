from datetime import datetime
from email.utils import formataddr
from typing import Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.email_event import EmailEvent
from models.enums import Direction
from models.mailbox import Mailbox
from models.sent_email import SentEmail
from services.email_providers.email_provider import SendResult
from services.email_providers.utils import html_to_text

SNIPPET_CHARS = 200


async def our_threads(db: AsyncSession, mailbox_id: int, thread_ids: Iterable[str]) -> set[str]:
    wanted = {thread_id for thread_id in thread_ids if thread_id}
    if not wanted:
        return set()
    return set(
        (
            await db.scalars(
                select(SentEmail.thread_id)
                .where(SentEmail.mailbox_id == mailbox_id, SentEmail.thread_id.in_(wanted))
                .distinct()
            )
        ).all()
    )


async def thread_events(db: AsyncSession, mailbox_id: int, thread_id: str) -> list[EmailEvent]:
    return list(
        (
            await db.scalars(
                select(EmailEvent)
                .where(EmailEvent.mailbox_id == mailbox_id, EmailEvent.thread_id == thread_id)
                .order_by(EmailEvent.sent_at, EmailEvent.id)
            )
        ).all()
    )


def thread_references(events: Sequence[EmailEvent]) -> list[str]:
    return list(dict.fromkeys(e.internet_message_id for e in events if e.internet_message_id))


async def record_outbound(
    db: AsyncSession,
    *,
    mailbox: Mailbox,
    result: SendResult,
    subject: str,
    html: str,
    from_name: Optional[str],
    to: Sequence[str],
    cc: Sequence[str],
    sent_email_id: Optional[int],
    user_contact_id: Optional[int],
    now: datetime,
) -> None:
    await db.execute(
        pg_insert(EmailEvent)
        .values(
            user_id=mailbox.user_id,
            mailbox_id=mailbox.id,
            provider=mailbox.provider,
            provider_message_id=result.provider_message_id,
            internet_message_id=result.internet_message_id or None,
            thread_id=result.thread_id,
            direction=Direction.OUTBOUND,
            from_address=formataddr((from_name, mailbox.email)),
            to_addresses=[address.lower() for address in to],
            cc_addresses=[address.lower() for address in cc],
            subject=subject,
            snippet=html_to_text(html)[:SNIPPET_CHARS],
            body_html=html,
            sent_at=now,
            sent_email_id=sent_email_id,
            user_contact_id=user_contact_id,
        )
        .on_conflict_do_nothing(index_elements=["provider", "provider_message_id"])
    )
