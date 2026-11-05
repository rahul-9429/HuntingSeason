import logging
from datetime import datetime, timezone
from email.utils import parseaddr

from sqlalchemy import select, update

from db.session import AsyncSessionLocal
from models.email_event import EmailEvent
from models.enums import MailboxStatus, ProposalStatus
from models.reply_proposal import ReplyProposal
from services import mailbox_manager
from services.email_event.proposal_worker import expire_thread_proposals, newer_message_in_thread
from services.email_event.threads import record_outbound, thread_events, thread_references
from services.email_providers.email_provider import get_email_provider
from services.email_providers.utils import build_quote_text
from services.outreach import limits
from services.outreach.drafting import (
    default_signature,
    paragraphs_html,
    strip_sign_off,
    with_signature,
)
from services.outreach.settings import get_settings
from services.outreach.user_info import get_user_info

logger = logging.getLogger(__name__)


class ProposalError(Exception):
    def __init__(self, detail: str, status_code: int):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


async def send(user_id: int, proposal_id: int) -> ReplyProposal:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        proposal = await db.scalar(
            select(ReplyProposal).where(
                ReplyProposal.id == proposal_id, ReplyProposal.user_id == user_id
            )
        )
        if proposal is None:
            raise ProposalError("Draft not found", 404)
        if proposal.status != ProposalStatus.PENDING:
            raise ProposalError(f"This draft is already {proposal.status.value}", 409)
        event = await db.get(EmailEvent, proposal.email_event_id)
        if proposal.expires_at <= now or (
            event is not None and await newer_message_in_thread(db, event)
        ):
            await db.execute(
                update(ReplyProposal)
                .where(ReplyProposal.id == proposal_id, ReplyProposal.status == ProposalStatus.PENDING)
                .values(status=ProposalStatus.EXPIRED, resolved_at=now)
            )
            await db.commit()
            raise ProposalError("This draft is out of date: it expired or the thread moved on", 409)

        mailbox = await mailbox_manager.get_for_user(db, user_id)
        if mailbox is None or mailbox.status != MailboxStatus.ACTIVE:
            raise ProposalError("The mailbox isn't active", 409)
        if event is None or event.mailbox_id != mailbox.id:
            raise ProposalError("This draft answers an email in a mailbox that's no longer connected", 409)
        settings = await get_settings(db, user_id)
        user_info = await get_user_info(db, user_id)
        references = thread_references(await thread_events(db, mailbox.id, event.thread_id))

        day = await limits.reserve_reply(
            db, user_id, limits.daily_cap(mailbox.warmup_started_at, now)
        )
        if day is None:
            raise ProposalError("Today's sending limit is used up", 429)
        claimed = (
            await db.execute(
                update(ReplyProposal)
                .where(ReplyProposal.id == proposal_id, ReplyProposal.status == ProposalStatus.PENDING)
                .values(status=ProposalStatus.APPROVED, resolved_at=now, send_error=None)
                .returning(
                    ReplyProposal.subject,
                    ReplyProposal.body,
                    ReplyProposal.cc,
                    ReplyProposal.bcc,
                    ReplyProposal.sent_email_id,
                    ReplyProposal.user_contact_id,
                )
            )
        ).first()
        await db.commit()
        if claimed is None:
            await limits.release(db, user_id, day)
            raise ProposalError("This draft was already handled", 409)
    subject, body, cc, bcc, sent_email_id, user_contact_id = claimed

    recipient = parseaddr(event.from_address)[1]
    from_name = settings.sender_name or mailbox.from_name
    try:
        html = with_signature(
            paragraphs_html(strip_sign_off(body)),
            settings.signature_html or default_signature(mailbox, user_info),
        )
        result = await get_email_provider(mailbox).send_reply(
            reply_to_provider_message_id=event.provider_message_id,
            reply_to_internet_message_id=event.internet_message_id or "",
            references=references,
            thread_id=event.thread_id,
            to=recipient,
            subject=subject,
            html=html,
            from_name=from_name,
            cc=cc,
            bcc=bcc,
            quote_text=build_quote_text(event.body_html, event.from_address, event.sent_at),
        )
    except Exception as exc:
        async with AsyncSessionLocal() as db:
            await limits.release(db, user_id, day)
            await db.execute(
                update(ReplyProposal)
                .where(ReplyProposal.id == proposal_id, ReplyProposal.status == ProposalStatus.APPROVED)
                .values(status=ProposalStatus.PENDING, resolved_at=None, send_error=str(exc)[:500])
            )
            await db.commit()
        logger.warning(
            "Couldn't send reply draft %s: %s",
            proposal_id,
            exc,
            extra={"user_id": user_id, "proposal_id": proposal_id},
        )
        raise ProposalError(f"Couldn't send the reply: {exc}", 502) from exc

    try:
        async with AsyncSessionLocal() as db:
            sent_at = datetime.now(timezone.utc)
            await record_outbound(
                db,
                mailbox=mailbox,
                result=result,
                subject=subject,
                html=html,
                from_name=from_name,
                to=[recipient],
                cc=cc,
                sent_email_id=sent_email_id or event.sent_email_id,
                user_contact_id=user_contact_id,
                now=sent_at,
            )
            await expire_thread_proposals(db, mailbox.id, event.thread_id, sent_at)
            await db.commit()
    except Exception:
        logger.exception(
            "Reply draft %s was sent but not recorded",
            proposal_id,
            extra={"user_id": user_id, "proposal_id": proposal_id},
        )

    logger.info(
        "Sent reply draft %s", proposal_id, extra={"user_id": user_id, "proposal_id": proposal_id}
    )
    async with AsyncSessionLocal() as db:
        sent = await db.get(ReplyProposal, proposal_id)
        if sent is None:
            raise ProposalError("Draft not found", 404)
        return sent
