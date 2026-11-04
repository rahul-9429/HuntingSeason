import logging
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime
from typing import Any, Optional, cast

from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services.errors import ServiceError
from api.type_models.contacts import (
    CONTACT_TYPES,
    ContactCompany,
    ContactList,
    ContactOut,
    ContactSource,
    ContactStage,
    ContactType,
    Credits,
    OutreachRequest,
    RevealResponse,
    Signal,
)
from models.company import Company
from models.contact import Contact
from models.enums import MailboxStatus, OutreachStage
from models.user_company import UserCompany
from models.user_contact import UserContact
from services import mailbox_manager
from services.email_providers.utils import html_to_text, sanitize_email_html
from services.hunt import credits as apollo_credits
from services.hunt.reveal import reveal_contact
from services.hunter import bare_domain
from services.outreach import email_contacting

logger = logging.getLogger(__name__)

PAGE_SIZE = 25
MAX_PAGE_SIZE = 100

Row = tuple[UserContact, Contact, Company, list[str]]


class ContactNotFound(ServiceError):
    status_code = 404


class InvalidCursor(ServiceError):
    status_code = 400


Cursor = tuple[int, datetime, int]


def encode_cursor(link: UserContact) -> str:
    raw = f"{link.relevance}|{link.found_at.isoformat()}|{link.id}"
    return urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> Cursor:
    try:
        raw = urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        relevance, found_at, link_id = raw.split("|")
        return int(relevance), datetime.fromisoformat(found_at), int(link_id)
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidCursor("Invalid pagination cursor") from exc


def after_cursor(cursor: Cursor) -> ColumnElement[bool]:
    relevance, found_at, link_id = cursor
    same_rank = and_(UserContact.relevance == relevance, UserContact.found_at == found_at)
    return or_(
        UserContact.relevance < relevance,
        and_(UserContact.relevance == relevance, UserContact.found_at < found_at),
        and_(same_rank, UserContact.id > link_id),
    )


def _location(person: Contact) -> Optional[str]:
    parts = [p for p in (person.city, person.state, person.country) if p]
    return ", ".join(dict.fromkeys(parts)) or None


def _name(person: Contact) -> str:
    last = person.last_name if person.revealed_at else person.last_name_obfuscated
    return " ".join(p for p in (person.first_name, last) if p)


def _masked_email(person: Contact, domain: Optional[str]) -> Optional[str]:
    if person.revealed_at or not person.has_email:
        return None
    return f"••••@{domain}" if domain else "••••••••"


def _signals(company: Company, roles: list[str], person: Contact) -> list[Signal]:
    hiring = (
        f"{company.name} is hiring for {', '.join(roles[:3])}"
        if roles
        else f"{company.name} is actively hiring"
    )
    signals = [Signal(kind="hiring", label=hiring)]
    if person.source == "tavily":
        signals.append(
            Signal(kind="activity", label="Found by web search, check their profile is current")
        )
    return signals


def to_contact_out(link: UserContact, person: Contact, company: Company, roles: list[str]) -> ContactOut:
    domain = bare_domain(company.domain)
    return ContactOut(
        id=str(link.id),
        name=_name(person),
        title=person.title or "",
        type=cast(ContactType, link.type),
        company_id=company.apollo_org_id,
        location=_location(person),
        email=person.email if person.revealed_at else None,
        email_masked=_masked_email(person, domain),
        linkedin=person.linkedin_url,
        photo_url=person.photo_url,
        relevance=link.relevance,
        signals=_signals(company, roles, person),
        found_at=link.found_at,
        stage=cast(ContactStage, link.stage),
        revealed=person.revealed_at is not None,
        source=cast(ContactSource, person.source),
        email_source=cast(Optional[ContactSource], person.email_source if person.revealed_at else None),
        company=ContactCompany(
            id=company.apollo_org_id,
            name=company.name,
            domain=domain,
            logo_url=company.logo_url,
            linkedin_url=company.linkedin_url,
        ),
    )


def contact_rows(user_id: int) -> Select[Any]:
    return (
        select(UserContact, Contact, Company, UserCompany.roles)
        .join(Contact, Contact.id == UserContact.contact_id)
        .join(UserCompany, UserCompany.id == UserContact.user_company_id)
        .join(Company, Company.id == UserCompany.company_id)
        .where(UserContact.user_id == user_id)
    )


async def list_contacts(
    db: AsyncSession,
    user_id: int,
    contact_type: Optional[ContactType],
    limit: int = PAGE_SIZE,
    cursor: Optional[str] = None,
) -> ContactList:
    query = contact_rows(user_id).order_by(
        UserContact.relevance.desc(), UserContact.found_at.desc(), UserContact.id
    )
    if contact_type is not None:
        query = query.where(UserContact.type == contact_type)
    if cursor is not None:
        query = query.where(after_cursor(decode_cursor(cursor)))
    page = (await db.execute(query.limit(limit + 1))).tuples().all()
    rows, has_more = page[:limit], len(page) > limit

    by_type = dict(
        (
            await db.execute(
                select(UserContact.type, func.count())
                .where(UserContact.user_id == user_id)
                .group_by(UserContact.type)
            )
        )
        .tuples()
        .all()
    )
    counts: dict[str, int] = {kind: by_type.get(kind, 0) for kind in CONTACT_TYPES}
    return ContactList(
        items=[to_contact_out(*row) for row in rows],
        counts={"all": sum(counts.values()), **counts},
        next_cursor=encode_cursor(rows[-1][0]) if has_more else None,
    )


async def credits(db: AsyncSession, user_id: int) -> Credits:
    balance, granted = await apollo_credits.wallet(db, user_id)
    return Credits(used=max(0, granted - balance), total=granted)


async def reveal(db: AsyncSession, user_id: int, user_contact_id: int) -> RevealResponse:
    row = (await db.execute(contact_rows(user_id).where(UserContact.id == user_contact_id))).tuples().first()
    if row is None:
        raise ContactNotFound("Contact not found")
    link, person, company, roles = row

    if person.revealed_at is None:
        await reveal_contact(db, user_id, person.id, bare_domain(company.domain))
        await db.refresh(person)

    return RevealResponse(
        contact=to_contact_out(link, person, company, roles),
        credits=await credits(db, user_id),
    )


async def send_outreach(
    db: AsyncSession, user_id: int, user_contact_id: int, req: OutreachRequest
) -> RevealResponse:
    row = (await db.execute(contact_rows(user_id).where(UserContact.id == user_contact_id))).tuples().first()
    if row is None:
        raise ContactNotFound("Contact not found")
    link, person, company, roles = row
    subject = " ".join(req.subject.split())
    html = sanitize_email_html(req.html)
    if not subject or not html_to_text(html):
        raise ServiceError("Write a subject and a message first", status_code=400)
    mailbox = await mailbox_manager.get_for_user(db, user_id)
    if mailbox is None or mailbox.status != MailboxStatus.ACTIVE:
        raise ServiceError("Connect or reconnect your mailbox first", status_code=409)
    if link.stage != OutreachStage.NEW:
        raise ServiceError("You've already emailed this person", status_code=409)

    if person.revealed_at is None:
        await reveal_contact(db, user_id, person.id, bare_domain(company.domain))
        await db.refresh(person)
    if not person.email:
        raise ServiceError("There's no verified email for this person", status_code=409)

    await email_contacting.send_written(
        user_id, link.id, subject, html, req.writer, req.template_id
    )
    await db.refresh(link)
    return RevealResponse(
        contact=to_contact_out(link, person, company, roles),
        credits=await credits(db, user_id),
    )
