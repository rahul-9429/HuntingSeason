from datetime import datetime
from email.utils import parseaddr
from typing import Mapping, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import Direction, OutreachStage
from models.user_contact import UserContact

_MAILER_DAEMONS = {"mailer-daemon", "postmaster"}
_AUTOMATIC_FLAGS = ("x-autoreply", "x-autorespond", "x-ms-exchange-message-is-ndr")


def set_stage(contact: UserContact, stage: OutreachStage, now: datetime) -> None:
    if contact.stage != stage:
        contact.stage = stage
        contact.stage_changed_at = now


def is_mailer_daemon(from_address: str) -> bool:
    local = parseaddr(from_address)[1].lower().split("@", 1)[0]
    return local in _MAILER_DAEMONS or local.startswith("microsoftexchange")


def is_automatic(headers: Mapping[str, str]) -> bool:
    submitted = headers.get("auto-submitted", "").strip().lower()
    if submitted and submitted != "no":
        return True
    if any(flag in headers for flag in _AUTOMATIC_FLAGS):
        return True
    return headers.get("precedence", "").strip().lower() == "auto_reply"


def went_quiet(contact: UserContact) -> bool:
    return (
        contact.stage == OutreachStage.DEAD
        and not contact.ai_stops_outreach
        and contact.replied_at is None
    )


async def apply_sync_transition(
    db: AsyncSession,
    *,
    user_contact_id: Optional[int],
    direction: Direction,
    from_address: str,
    sent_at: datetime,
    now: datetime,
    automatic: bool = False,
) -> None:
    if user_contact_id is None:
        return
    contact = await db.get(UserContact, user_contact_id, with_for_update=True)
    if contact is None:
        return

    if direction == Direction.OUTBOUND:
        if went_quiet(contact):
            set_stage(contact, OutreachStage.CONTACTED, now)
            contact.follow_up_count = 0
        if contact.stage == OutreachStage.CONTACTED:
            contact.last_contacted_at = max(contact.last_contacted_at or sent_at, sent_at)
        return

    if automatic or is_mailer_daemon(from_address):
        return
    quiet = went_quiet(contact)
    contact.replied_at = now
    if contact.stage == OutreachStage.CONTACTED or quiet:
        set_stage(contact, OutreachStage.HOT, now)
    if quiet:
        contact.follow_up_count = 0
