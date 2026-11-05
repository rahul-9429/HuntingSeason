from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import ColumnElement, Select, and_, func, literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from models.company import Company
from models.contact import Contact
from models.emailed_address import EmailedAddress
from models.enums import OutreachStage
from models.outreach_settings import OutreachSettings
from models.user_company import UserCompany
from models.user_contact import UserContact
from services.outreach.names import extract_first_name

INVALID_EMAIL_STATUS = "invalid"

NEVER_SEND_LOCAL_PARTS = (
    "abuse",
    "postmaster",
    "mailer-daemon",
    "noreply",
    "no-reply",
    "donotreply",
    "bounce",
    "bounces",
)

PUBLIC_MAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "msn.com",
        "yahoo.com",
        "icloud.com",
        "me.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
    }
)

_RECIPIENT_TYPES = {
    "hiring_manager": "hiring manager",
    "recruiter": "recruiter",
    "referrer": "potential referrer (a peer at the company)",
}


@dataclass(frozen=True)
class Lead:
    user_contact: UserContact
    contact: Contact
    company: Company
    roles: list[str]
    locations: list[str]

    @property
    def email(self) -> str:
        return self.contact.email or ""

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.contact.first_name, self.contact.last_name) if part)

    @property
    def first_name(self) -> str:
        return extract_first_name(self.full_name, self.email)

    @property
    def recipient_type(self) -> str:
        return _RECIPIENT_TYPES.get(self.user_contact.type, self.user_contact.type)


def mailbox_domain(mailbox_email: str) -> str:
    return mailbox_email.rsplit("@", 1)[-1].lower()


def _leads(user_id: int) -> Select[Any]:
    return (
        select(UserContact, Contact, Company, UserCompany.roles, UserCompany.locations)
        .join(Contact, Contact.id == UserContact.contact_id)
        .join(UserCompany, UserCompany.id == UserContact.user_company_id)
        .join(Company, Company.id == UserCompany.company_id)
        .where(UserContact.user_id == user_id)
    )


def _sendable(own_domain: str) -> ColumnElement[bool]:
    email = func.lower(Contact.email)
    conditions = [
        Contact.email.is_not(None),
        func.coalesce(Contact.email_status, "") != INVALID_EMAIL_STATUS,
        UserContact.ai_stops_outreach.is_(False),
        UserContact.replied_at.is_(None),
        func.split_part(email, "@", 1).not_in(NEVER_SEND_LOCAL_PARTS),
    ]
    if own_domain not in PUBLIC_MAIL_DOMAINS:
        conditions.append(func.split_part(email, "@", 2) != own_domain)
    return and_(*conditions)


def leads_with_email(user_id: int) -> Select[Any]:
    return _leads(user_id).where(Contact.email.is_not(None))


def first_touch_query(user_id: int, own_domain: str) -> Select[Any]:
    already_emailed = (
        select(EmailedAddress.email)
        .where(
            EmailedAddress.user_id == UserContact.user_id,
            EmailedAddress.email == func.lower(Contact.email),
        )
        .exists()
    )
    return _leads(user_id).where(
        UserContact.stage == OutreachStage.NEW, _sendable(own_domain), ~already_emailed
    )


def follow_up_query(
    user_id: int, own_domain: str, settings: OutreachSettings, now: datetime
) -> Select[Any]:
    return _leads(user_id).where(
        UserContact.stage == OutreachStage.CONTACTED,
        UserContact.follow_up_count < settings.max_follow_ups,
        UserContact.last_contacted_at <= now - timedelta(days=settings.follow_up_interval_days),
        _sendable(own_domain),
    )


def _key(after: tuple[datetime, int]) -> ColumnElement[Any]:
    return tuple_(literal(after[0]), literal(after[1]))


def _to_lead(row: Any) -> Lead:
    user_contact, contact, company, roles, locations = row
    return Lead(
        user_contact=user_contact,
        contact=contact,
        company=company,
        roles=list(roles or []),
        locations=list(locations or []),
    )


async def first_touch_page(
    db: AsyncSession,
    user_id: int,
    own_domain: str,
    after: Optional[tuple[datetime, int]],
    limit: int,
) -> list[Lead]:
    query = first_touch_query(user_id, own_domain)
    if after is not None:
        query = query.where(tuple_(UserContact.found_at, UserContact.id) > _key(after))
    rows = await db.execute(query.order_by(UserContact.found_at, UserContact.id).limit(limit))
    return [_to_lead(row) for row in rows.tuples()]


async def follow_up_page(
    db: AsyncSession,
    user_id: int,
    own_domain: str,
    settings: OutreachSettings,
    now: datetime,
    after: Optional[tuple[datetime, int]],
    limit: int,
) -> list[Lead]:
    query = follow_up_query(user_id, own_domain, settings, now)
    if after is not None:
        query = query.where(tuple_(UserContact.last_contacted_at, UserContact.id) > _key(after))
    rows = await db.execute(
        query.order_by(UserContact.last_contacted_at, UserContact.id).limit(limit)
    )
    return [_to_lead(row) for row in rows.tuples()]


async def one(db: AsyncSession, query: Select[Any], user_contact_id: int) -> Optional[Lead]:
    row = (
        await db.execute(
            query.where(UserContact.id == user_contact_id).execution_options(populate_existing=True)
        )
    ).first()
    return _to_lead(row) if row else None


async def any_match(db: AsyncSession, query: Select[Any]) -> bool:
    return (await db.execute(query.limit(1))).first() is not None
