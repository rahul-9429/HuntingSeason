import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.contact import Contact
from services import hunter
from services.errors import ServiceError
from services.hunt import apollo, credits
from services.hunter import HunterError
from services.schemas.common import http_url, str_or_none

logger = logging.getLogger(__name__)


class ContactNotFound(ServiceError):
    status_code = 404


def _apply_match(person: Contact, match: dict[str, Any]) -> None:
    person.first_name = str_or_none(match.get("first_name")) or person.first_name
    person.last_name = str_or_none(match.get("last_name"))
    person.title = str_or_none(match.get("title")) or person.title
    person.seniority = str_or_none(match.get("seniority"))
    person.email_status = str_or_none(match.get("email_status"))
    person.email = str_or_none(match.get("email")) if person.email_status == "verified" else None
    person.email_source = "apollo" if person.email else None
    person.linkedin_url = http_url(match.get("linkedin_url"))
    person.photo_url = http_url(match.get("photo_url"))
    person.city = str_or_none(match.get("city"))
    person.state = str_or_none(match.get("state"))
    person.country = str_or_none(match.get("country"))
    person.revealed_at = datetime.now(timezone.utc)


async def email_from_hunter(person: Contact, domain: Optional[str]) -> None:
    if person.email or not domain or not person.last_name or not hunter.configured():
        return
    try:
        email = await hunter.find_email(domain, person.first_name, person.last_name)
    except HunterError as exc:
        logger.warning(
            "Hunter email lookup for contact %s failed: %s",
            person.id,
            exc.detail,
            extra={"contact_id": person.id, "domain": domain},
        )
        return
    if email:
        person.email, person.email_status, person.email_source = email, "valid", "hunter"
        person.has_email = True


async def _reveal_person(db: AsyncSession, contact_id: int, domain: Optional[str]) -> bool:
    person = (
        await db.execute(
            select(Contact)
            .where(Contact.id == contact_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    if person.revealed_at is not None or person.apollo_person_id is None:
        return False

    matches = await apollo.match_people([person.apollo_person_id])
    if not matches:
        raise ContactNotFound("Apollo no longer has this person's details")
    _apply_match(person, matches[0])
    await email_from_hunter(person, domain)
    await db.commit()
    return True


async def reveal_contact(
    db: AsyncSession, user_id: int, contact_id: int, domain: Optional[str]
) -> None:
    await credits.reserve_credit(db, user_id, f"revealing contact {contact_id}")
    try:
        charged = await _reveal_person(db, contact_id, domain)
    except Exception:
        await db.rollback()
        await credits.refund_credit(db, user_id)
        raise
    if not charged:
        await db.commit()
        await credits.refund_credit(db, user_id)
