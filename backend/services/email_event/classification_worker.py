import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import AsyncSessionLocal
from models.contact import Contact
from models.email_event import EmailEvent
from models.enums import DeliveryStatus, Direction, OutreachStage, ReplyLabel
from models.sent_email import SentEmail
from models.user_contact import UserContact
from services.email_event import openai_client, proposal_worker
from services.email_event.openai_client import LLMError
from services.email_event.prompts import CLASSIFY_EMAIL_PROMPT
from services.email_event.status_transition import set_stage
from services.email_providers.utils import html_to_text
from services.outreach.eligibility import INVALID_EMAIL_STATUS
from services.schemas.outreach import Classification

logger = logging.getLogger(__name__)

EMAIL_TEXT_CHARS = 4000
_DSN_STATUS = re.compile(r"\b([45])\.\d{1,3}\.\d{1,3}\b")


def is_hard_bounce(subject: str, body_text: str) -> bool:
    for text in (subject, body_text):
        match = _DSN_STATUS.search(text)
        if match:
            return match.group(1) == "5"
    return True


async def classify(event_id: int) -> None:
    async with AsyncSessionLocal() as db:
        event = await db.get(EmailEvent, event_id)
    if event is None or event.direction != Direction.INBOUND or event.user_contact_id is None:
        return

    email_text = (
        f"From: {event.from_address}\nTo: {', '.join(event.to_addresses)}\n"
        f"Subject: {event.subject}\n\n" + html_to_text(event.body_html)[:EMAIL_TEXT_CHARS]
    )
    try:
        result = await openai_client.generate_structured(
            system="You are a strict classifier.",
            user=f"{CLASSIFY_EMAIL_PROMPT}\n\nEmail:\n{email_text}",
            schema=Classification,
            user_id=event.user_id,
            purpose="Reply classification",
        )
    except LLMError:
        logger.warning(
            "Left email event %s unclassified",
            event_id,
            extra={"email_event_id": event_id, "user_id": event.user_id},
        )
        return

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        event = await db.get(EmailEvent, event_id, with_for_update=True)
        if event is None:
            return
        event.classification_label = result.type
        event.classification_reason = result.reason
        event.classified_at = now
        await _apply(db, event, result.type, now)
        await db.commit()
    logger.info(
        "Email event %s classified as %s",
        event_id,
        result.type.value,
        extra={"email_event_id": event_id, "user_id": event.user_id, "label": result.type.value},
    )

    if result.type in (ReplyLabel.INQUIRY, ReplyLabel.REFERRAL):
        await proposal_worker.create_proposal(event_id)


async def _apply(db: AsyncSession, event: EmailEvent, label: ReplyLabel, now: datetime) -> None:
    contact = (
        await db.get(UserContact, event.user_contact_id, with_for_update=True)
        if event.user_contact_id is not None
        else None
    )
    if contact is None:
        return

    if label == ReplyLabel.INQUIRY:
        set_stage(contact, OutreachStage.HOT, now)
    elif label == ReplyLabel.REFERRAL:
        contact.ai_stops_outreach = True
    elif label in (ReplyLabel.NOT_INTERESTED, ReplyLabel.DISQUALIFIED):
        set_stage(contact, OutreachStage.DEAD, now)
        contact.ai_stops_outreach = True
    elif label == ReplyLabel.BOUNCED:
        body_text = html_to_text(event.body_html)
        address = await db.scalar(select(Contact.email).where(Contact.id == contact.contact_id))
        if not address or address.lower() not in f"{event.subject}\n{body_text}".lower():
            logger.info(
                "Bounce in email event %s isn't for the contact's address; ignoring it",
                event.id,
                extra={"email_event_id": event.id, "user_id": event.user_id},
            )
            return
        hard = is_hard_bounce(event.subject, body_text)
        if event.sent_email_id is not None:
            await db.execute(
                update(SentEmail)
                .where(SentEmail.id == event.sent_email_id)
                .values(
                    delivery_status=DeliveryStatus.BOUNCED_HARD if hard else DeliveryStatus.BOUNCED_SOFT
                )
            )
        if hard:
            await db.execute(
                update(Contact)
                .where(Contact.id == contact.contact_id)
                .values(email_status=INVALID_EMAIL_STATUS)
            )
            set_stage(contact, OutreachStage.DEAD, now)
            contact.ai_stops_outreach = True
