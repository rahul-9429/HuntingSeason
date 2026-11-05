import logging
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import AsyncSessionLocal
from models.company import Company
from models.contact import Contact
from models.email_event import EmailEvent
from models.enums import ProposalStatus, ReplyLabel
from models.mailbox import Mailbox
from models.reply_proposal import ReplyProposal
from models.sent_email import SentEmail
from models.user_company import UserCompany
from models.user_contact import UserContact
from services.email_event import openai_client, prompts
from services.email_event.openai_client import LLMError
from services.email_event.prompts import fill
from services.email_event.threads import thread_events
from services.email_providers.utils import html_to_text
from services.outreach.drafting import reply_subject, style_guard
from services.outreach.names import extract_first_name
from services.outreach.settings import get_settings
from services.outreach.user_info import get_user_info
from services.schemas.outreach import ReplyDraft

logger = logging.getLogger(__name__)

EXPIRES_AFTER = timedelta(days=7)
AUTO_SEND_AFTER = timedelta(hours=24)
THREAD_CHARS = 6000


async def expire_thread_proposals(
    db: AsyncSession, mailbox_id: int, thread_id: str, now: datetime
) -> None:
    await db.execute(
        update(ReplyProposal)
        .where(
            ReplyProposal.status == ProposalStatus.PENDING,
            ReplyProposal.email_event_id.in_(
                select(EmailEvent.id).where(
                    EmailEvent.mailbox_id == mailbox_id, EmailEvent.thread_id == thread_id
                )
            ),
        )
        .values(status=ProposalStatus.EXPIRED, resolved_at=now)
    )


async def newer_message_in_thread(db: AsyncSession, event: EmailEvent) -> bool:
    newer = await db.scalar(
        select(EmailEvent.id)
        .where(
            EmailEvent.mailbox_id == event.mailbox_id,
            EmailEvent.thread_id == event.thread_id,
            EmailEvent.sent_at > event.sent_at,
        )
        .limit(1)
    )
    return newer is not None


def _thread_text(events: Sequence[EmailEvent]) -> str:
    blocks = [
        f"From: {event.from_address}\nDate: {event.sent_at:%Y-%m-%d %H:%M} UTC\n\n"
        f"{html_to_text(event.body_html)}"
        for event in events
    ]
    while len(blocks) > 1 and sum(len(block) + 2 for block in blocks) > THREAD_CHARS:
        blocks.pop(0)
    return "\n\n".join(blocks)[-THREAD_CHARS:] or "(none)"


async def create_proposal(event_id: int) -> None:
    async with AsyncSessionLocal() as db:
        event = await db.get(EmailEvent, event_id)
        if (
            event is None
            or event.classification_label not in (ReplyLabel.INQUIRY, ReplyLabel.REFERRAL)
            or event.user_contact_id is None
            or event.mailbox_id is None
        ):
            return
        label = event.classification_label
        lead = (
            await db.execute(
                select(UserContact, Contact, Company)
                .join(Contact, Contact.id == UserContact.contact_id)
                .join(UserCompany, UserCompany.id == UserContact.user_company_id)
                .join(Company, Company.id == UserCompany.company_id)
                .where(UserContact.id == event.user_contact_id)
            )
        ).first()
        mailbox = await db.get(Mailbox, event.mailbox_id)
        if lead is None or mailbox is None:
            return
        user_contact, contact, company = lead
        settings = await get_settings(db, event.user_id)
        user_info = await get_user_info(db, event.user_id)
        first_email = await db.scalar(
            select(SentEmail)
            .where(SentEmail.mailbox_id == mailbox.id, SentEmail.thread_id == event.thread_id)
            .order_by(SentEmail.follow_up_attempt, SentEmail.sent_at)
            .limit(1)
        )
        earlier = [e for e in await thread_events(db, mailbox.id, event.thread_id) if e.id != event.id]

    full_name = " ".join(part for part in (contact.first_name, contact.last_name) if part)
    first_name = extract_first_name(full_name, contact.email or "")
    if label == ReplyLabel.INQUIRY:
        label_rule = prompts.REPLY_RULE_INQUIRY
        if settings.reply_booking_link:
            label_rule += fill(prompts.REPLY_RULE_BOOKING_LINK, link=settings.reply_booking_link)
    else:
        label_rule = prompts.REPLY_RULE_REFERRAL
    booking_link_line = (
        f"\nBooking link: {settings.reply_booking_link}\n"
        if label == ReplyLabel.INQUIRY and settings.reply_booking_link
        else ""
    )

    try:
        draft = await openai_client.generate_structured(
            system=fill(prompts.REPLY_DRAFT_SYSTEM, label_rule=label_rule, first_name=first_name),
            user=fill(
                prompts.REPLY_DRAFT_USER,
                label=label.value,
                reason=event.classification_reason or "",
                first_name=first_name,
                title=contact.title or "their team",
                company=company.name,
                subject=event.subject,
                user_info=user_info.as_prompt(),
                reply_facts=settings.reply_facts or "(none)",
                booking_link_line=booking_link_line,
                first_email=html_to_text(first_email.body_html) if first_email else "(not found)",
                thread=_thread_text(earlier),
                inbound=html_to_text(event.body_html),
            ),
            schema=ReplyDraft,
            user_id=event.user_id,
            purpose="Reply draft",
        )
    except LLMError:
        logger.warning(
            "No reply draft for email event %s",
            event_id,
            extra={"email_event_id": event_id, "user_id": event.user_id},
        )
        return

    body = style_guard(draft.body.strip(), user_id=event.user_id, field="reply body")
    subject = reply_subject(
        style_guard(draft.subject.strip() or event.subject, user_id=event.user_id, field="reply subject")
    )
    excluded = {mailbox.email.lower(), parseaddr(event.from_address)[1].lower()}
    cc = [a for a in dict.fromkeys([*event.cc_addresses, *settings.reply_cc]) if a.lower() not in excluded]
    now = datetime.now(timezone.utc)
    auto_send = settings.auto_send_replies and label != ReplyLabel.REFERRAL

    async with AsyncSessionLocal() as db:
        if await newer_message_in_thread(db, event):
            logger.info(
                "Dropped the reply draft for email event %s: the thread has moved on",
                event_id,
                extra={"email_event_id": event_id, "user_id": event.user_id},
            )
            return
        await db.execute(
            pg_insert(ReplyProposal)
            .values(
                user_id=event.user_id,
                user_contact_id=user_contact.id,
                email_event_id=event.id,
                sent_email_id=event.sent_email_id,
                label=label,
                reason=event.classification_reason or "",
                subject=subject,
                body=body,
                cc=cc,
                bcc=list(settings.reply_bcc),
                status=ProposalStatus.PENDING,
                auto_send_at=now + AUTO_SEND_AFTER if auto_send else None,
                expires_at=now + EXPIRES_AFTER,
            )
            .on_conflict_do_nothing(index_elements=["email_event_id"])
        )
        await db.commit()
    logger.info(
        "Drafted a reply to email event %s",
        event_id,
        extra={"email_event_id": event_id, "user_id": event.user_id, "auto_send": auto_send},
    )
