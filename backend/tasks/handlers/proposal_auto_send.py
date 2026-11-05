import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update

from db.session import AsyncSessionLocal
from models.contact import Contact
from models.enums import ProposalStatus
from models.outreach_settings import OutreachSettings
from models.reply_proposal import ReplyProposal
from models.user_contact import UserContact
from services.email_event import proposals
from services.outreach.country_business_hours import is_country_send_allowed

logger = logging.getLogger(__name__)


async def _wait_for_user(proposal_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(ReplyProposal).where(ReplyProposal.id == proposal_id).values(auto_send_at=None)
        )
        await db.commit()


async def handle(payload: dict[str, Any]) -> None:
    async with AsyncSessionLocal() as db:
        due = (
            await db.execute(
                select(
                    ReplyProposal.id,
                    ReplyProposal.user_id,
                    OutreachSettings.auto_send_replies,
                    OutreachSettings.email_send_schedule_enabled,
                    OutreachSettings.email_send_schedule,
                    Contact.country,
                )
                .outerjoin(OutreachSettings, OutreachSettings.user_id == ReplyProposal.user_id)
                .outerjoin(UserContact, UserContact.id == ReplyProposal.user_contact_id)
                .outerjoin(Contact, Contact.id == UserContact.contact_id)
                .where(
                    ReplyProposal.status == ProposalStatus.PENDING,
                    ReplyProposal.auto_send_at <= datetime.now(timezone.utc),
                )
                .order_by(ReplyProposal.auto_send_at)
            )
        ).tuples().all()

    held = 0
    for proposal_id, user_id, auto_send_on, schedule_on, overrides, country in due:
        if not auto_send_on:
            await _wait_for_user(proposal_id)
            continue
        if schedule_on and not is_country_send_allowed(
            country, overrides or {}, datetime.now(timezone.utc)
        ):
            held += 1
            continue
        try:
            await proposals.send(user_id, proposal_id)
        except proposals.ProposalError as exc:
            logger.warning(
                "Auto-send of reply draft %s failed, leaving it for the user: %s",
                proposal_id,
                exc.detail,
                extra={"user_id": user_id, "proposal_id": proposal_id},
            )
            await _wait_for_user(proposal_id)
    if held:
        logger.info(
            "%d reply drafts held for the recipient's local business hours",
            held,
            extra={"skipped_by_schedule": held},
        )
