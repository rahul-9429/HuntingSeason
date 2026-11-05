import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Any, Optional, Sequence

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from api.api_services.contacts import contact_rows, to_contact_out
from api.api_services.errors import ServiceError
from api.type_models.contacts import CONTACT_TYPES, ContactOut
from api.type_models.threads import (
    InboxFilter,
    LastMessage,
    MessageOut,
    ReplyDraftOut,
    Sender,
    ThreadList,
    ThreadOut,
    ThreadPatch,
    ThreadSummary,
)
from models.email_event import EmailEvent
from models.enums import Direction, MailboxStatus, ProposalStatus
from models.inbox_thread import InboxThread
from models.mailbox import Mailbox
from models.reply_proposal import ReplyProposal
from models.user_contact import UserContact
from services import mailbox_manager
from services.email_event.proposal_worker import expire_thread_proposals
from services.email_event.status_transition import apply_sync_transition, is_mailer_daemon
from services.email_event.threads import record_outbound, thread_events, thread_references
from services.email_providers.email_provider import (
    MailboxAuthError,
    ProviderConfigError,
    get_email_provider,
)
from services.email_providers.utils import build_quote_text, html_to_text, strip_quoted_reply
from services.outreach import limits
from services.outreach.drafting import paragraphs_html, reply_subject, with_signature
from services.outreach.settings import get_settings

logger = logging.getLogger(__name__)

MAX_THREADS = 1000
MAX_LISTED = 200
PREVIEW_CHARS = 200
NEVER = datetime.min.replace(tzinfo=timezone.utc)


@dataclass
class _Thread:
    mailbox: Mailbox
    thread_id: str
    events: list[EmailEvent]
    user_contact_id: int
    contact: ContactOut
    state: Optional[InboxThread]
    draft: Optional[ReplyProposal]


def _pending_draft(user_id: int) -> ColumnElement[bool]:
    return and_(
        ReplyProposal.user_id == user_id,
        ReplyProposal.status == ProposalStatus.PENDING,
        ReplyProposal.expires_at > func.now(),
    )


def _not_found() -> ServiceError:
    return ServiceError("Conversation not found", status_code=404)


def _text(html: str) -> str:
    return strip_quoted_reply(html_to_text(html))


def _sender(direction: Direction) -> Sender:
    return "me" if direction == Direction.OUTBOUND else "them"


def _unread(
    last_in: Optional[datetime], last_out: Optional[datetime], read_at: Optional[datetime]
) -> bool:
    return last_in is not None and last_in > (last_out or NEVER) and last_in > (read_at or NEVER)


def _archived(last_in: Optional[datetime], archived_at: Optional[datetime]) -> bool:
    return archived_at is not None and (last_in or NEVER) <= archived_at


def _empty_counts() -> dict[str, int]:
    return {"all": 0, "drafts": 0, **{kind: 0 for kind in CONTACT_TYPES}}


async def list_threads(
    db: AsyncSession, user_id: int, inbox_filter: InboxFilter, q: str
) -> ThreadList:
    counts = _empty_counts()
    mailbox = await mailbox_manager.get_for_user(db, user_id)
    if mailbox is None:
        return ThreadList(items=[], counts=counts, unread=0)

    stats = (
        select(
            EmailEvent.thread_id,
            func.min(EmailEvent.id).label("first_id"),
            func.max(EmailEvent.user_contact_id).label("user_contact_id"),
            func.max(EmailEvent.sent_at).label("updated_at"),
            func.max(EmailEvent.sent_at)
            .filter(EmailEvent.direction == Direction.INBOUND)
            .label("last_in"),
            func.max(EmailEvent.sent_at)
            .filter(EmailEvent.direction == Direction.OUTBOUND)
            .label("last_out"),
        )
        .where(EmailEvent.mailbox_id == mailbox.id)
        .group_by(EmailEvent.thread_id)
        .subquery()
    )
    last = (
        select(EmailEvent.thread_id, EmailEvent.direction, EmailEvent.body_html)
        .where(EmailEvent.mailbox_id == mailbox.id)
        .distinct(EmailEvent.thread_id)
        .order_by(EmailEvent.thread_id, EmailEvent.sent_at.desc(), EmailEvent.id.desc())
        .subquery()
    )
    first = aliased(EmailEvent)
    with_drafts = set(
        (
            await db.scalars(
                select(EmailEvent.thread_id)
                .join(ReplyProposal, ReplyProposal.email_event_id == EmailEvent.id)
                .where(EmailEvent.mailbox_id == mailbox.id, _pending_draft(user_id))
                .distinct()
            )
        ).all()
    )
    rows = (
        await db.execute(
            contact_rows(user_id)
            .add_columns(
                stats.c.thread_id,
                stats.c.first_id,
                stats.c.updated_at,
                stats.c.last_in,
                stats.c.last_out,
                first.subject.label("subject"),
                last.c.direction.label("last_direction"),
                last.c.body_html.label("last_body"),
                InboxThread.read_at,
                InboxThread.archived_at,
            )
            .join(stats, stats.c.user_contact_id == UserContact.id)
            .join(first, first.id == stats.c.first_id)
            .join(last, last.c.thread_id == stats.c.thread_id)
            .outerjoin(
                InboxThread,
                (InboxThread.mailbox_id == mailbox.id)
                & (InboxThread.thread_id == stats.c.thread_id),
            )
            .order_by(stats.c.updated_at.desc(), stats.c.first_id.desc())
            .limit(MAX_THREADS)
        )
    ).all()

    needle = q.strip().lower()
    items: list[ThreadSummary] = []
    unread = 0
    for row in rows:
        if _archived(row.last_in, row.archived_at):
            continue
        link: UserContact = row.UserContact
        has_draft = row.thread_id in with_drafts
        counts["all"] += 1
        counts[link.type] = counts.get(link.type, 0) + 1
        counts["drafts"] += has_draft
        is_unread = _unread(row.last_in, row.last_out, row.read_at)
        unread += is_unread
        if inbox_filter == "drafts":
            if not has_draft:
                continue
        elif inbox_filter != "all" and link.type != inbox_filter:
            continue
        contact = to_contact_out(link, row.Contact, row.Company, row.roles)
        if needle and needle not in f"{contact.name} {contact.company.name} {row.subject}".lower():
            continue
        if len(items) < MAX_LISTED:
            items.append(
                ThreadSummary(
                    id=str(row.first_id),
                    contact=contact,
                    subject=row.subject,
                    unread=is_unread,
                    has_draft=has_draft,
                    updated_at=row.updated_at,
                    last_message=LastMessage(
                        sender=_sender(row.last_direction),
                        body=_text(row.last_body)[:PREVIEW_CHARS],
                    ),
                )
            )
    return ThreadList(items=items, counts=counts, unread=unread)


async def _locate(db: AsyncSession, user_id: int, event_id: int) -> tuple[Mailbox, str]:
    mailbox = await mailbox_manager.get_for_user(db, user_id)
    if mailbox is None:
        raise _not_found()
    thread_id = await db.scalar(
        select(EmailEvent.thread_id).where(
            EmailEvent.id == event_id,
            EmailEvent.user_id == user_id,
            EmailEvent.mailbox_id == mailbox.id,
        )
    )
    if thread_id is None:
        raise _not_found()
    return mailbox, thread_id


async def _load(db: AsyncSession, user_id: int, event_id: int) -> _Thread:
    mailbox, thread_id = await _locate(db, user_id, event_id)
    events = await thread_events(db, mailbox.id, thread_id)
    user_contact_id = next(
        (event.user_contact_id for event in events if event.user_contact_id is not None), None
    )
    if user_contact_id is None:
        raise _not_found()
    row = (
        await db.execute(contact_rows(user_id).where(UserContact.id == user_contact_id))
    ).tuples().first()
    if row is None:
        raise _not_found()
    draft = await db.scalar(
        select(ReplyProposal)
        .join(EmailEvent, EmailEvent.id == ReplyProposal.email_event_id)
        .where(
            _pending_draft(user_id),
            EmailEvent.mailbox_id == mailbox.id,
            EmailEvent.thread_id == thread_id,
        )
        .order_by(ReplyProposal.created_at.desc())
        .limit(1)
    )
    return _Thread(
        mailbox=mailbox,
        thread_id=thread_id,
        events=events,
        user_contact_id=user_contact_id,
        contact=to_contact_out(*row),
        state=await db.get(InboxThread, (mailbox.id, thread_id)),
        draft=draft,
    )


def _last_at(events: Sequence[EmailEvent], direction: Direction) -> Optional[datetime]:
    return max((event.sent_at for event in events if event.direction == direction), default=None)


def _thread_out(thread: _Thread) -> ThreadOut:
    events, state = thread.events, thread.state
    first = min(events, key=lambda event: event.id)
    last_in = _last_at(events, Direction.INBOUND)
    return ThreadOut(
        id=str(first.id),
        contact_id=thread.contact.id,
        contact=thread.contact,
        subject=first.subject,
        unread=_unread(
            last_in, _last_at(events, Direction.OUTBOUND), state.read_at if state else None
        ),
        archived=_archived(last_in, state.archived_at if state else None),
        updated_at=events[-1].sent_at,
        notes=state.notes if state else "",
        messages=[
            MessageOut(
                id=str(event.id),
                sender=_sender(event.direction),
                body=_text(event.body_html),
                sent_at=event.sent_at,
            )
            for event in events
        ],
        draft=(
            ReplyDraftOut(
                id=str(thread.draft.id),
                label=thread.draft.label,
                reason=thread.draft.reason,
                subject=thread.draft.subject,
                body=thread.draft.body,
                auto_send_at=thread.draft.auto_send_at,
            )
            if thread.draft
            else None
        ),
    )


async def get(db: AsyncSession, user_id: int, event_id: int) -> ThreadOut:
    return _thread_out(await _load(db, user_id, event_id))


async def update(db: AsyncSession, user_id: int, event_id: int, patch: ThreadPatch) -> ThreadOut:
    mailbox, thread_id = await _locate(db, user_id, event_id)
    latest = await db.scalar(
        select(func.max(EmailEvent.sent_at)).where(
            EmailEvent.mailbox_id == mailbox.id, EmailEvent.thread_id == thread_id
        )
    )
    now = max(datetime.now(timezone.utc), latest or NEVER)
    values: dict[str, Any] = {}
    if patch.unread is not None:
        values["read_at"] = None if patch.unread else now
    if patch.archived is not None:
        values["archived_at"] = now if patch.archived else None
    if patch.notes is not None:
        values["notes"] = patch.notes
    if values:
        await db.execute(
            pg_insert(InboxThread)
            .values(mailbox_id=mailbox.id, thread_id=thread_id, **values)
            .on_conflict_do_update(
                index_elements=["mailbox_id", "thread_id"],
                set_={**values, "updated_at": func.now()},
            )
        )
        await db.commit()
    return await get(db, user_id, event_id)


def _recipient(events: Sequence[EmailEvent], contact_email: Optional[str]) -> Optional[str]:
    for event in reversed(events):
        if event.direction == Direction.INBOUND and not is_mailer_daemon(event.from_address):
            address = parseaddr(event.from_address)[1]
            if address:
                return address
    for event in events:
        if event.direction == Direction.OUTBOUND and event.to_addresses:
            return event.to_addresses[0]
    return contact_email


async def reply(db: AsyncSession, user_id: int, event_id: int, body: str) -> MessageOut:
    text = body.strip()
    if not text:
        raise ServiceError("Write something first", status_code=400)
    thread = await _load(db, user_id, event_id)
    mailbox, events = thread.mailbox, thread.events
    if mailbox.status != MailboxStatus.ACTIVE:
        raise ServiceError("Reconnect your mailbox to send", status_code=409)
    recipient = _recipient(events, thread.contact.email)
    if not recipient:
        raise ServiceError("This conversation has no address to reply to", status_code=409)
    target = next(
        (event for event in reversed(events) if not is_mailer_daemon(event.from_address)),
        events[-1],
    )

    settings = await get_settings(db, user_id)
    html = paragraphs_html(text)
    if settings.signature_html:
        html = with_signature(html, settings.signature_html)
    from_name = settings.sender_name or mailbox.from_name
    subject = reply_subject(min(events, key=lambda event: event.id).subject)
    references = thread_references(events)

    now = datetime.now(timezone.utc)
    day = await limits.reserve_reply(db, user_id, limits.daily_cap(mailbox.warmup_started_at, now))
    if day is None:
        raise ServiceError("Today's sending limit is used up", status_code=429)
    try:
        result = await get_email_provider(mailbox).send_reply(
            reply_to_provider_message_id=target.provider_message_id,
            reply_to_internet_message_id=target.internet_message_id or "",
            references=references,
            thread_id=thread.thread_id,
            to=recipient,
            subject=subject,
            html=html,
            from_name=from_name,
            quote_text=build_quote_text(target.body_html, target.from_address, target.sent_at),
        )
    except Exception as exc:
        await limits.release(db, user_id, day)
        logger.warning(
            "Couldn't send a reply in thread %s: %s",
            thread.thread_id,
            exc,
            extra={"user_id": user_id, "mailbox_id": mailbox.id},
        )
        if isinstance(exc, ProviderConfigError):
            raise ServiceError(
                "This mail provider isn't set up on the server", status_code=503
            ) from exc
        if isinstance(exc, MailboxAuthError):
            raise ServiceError(str(exc), status_code=409) from exc
        raise ServiceError("Couldn't send the reply. Try again.", status_code=502) from exc

    sent_at = datetime.now(timezone.utc)
    message_id: Optional[int] = None
    try:
        await record_outbound(
            db,
            mailbox=mailbox,
            result=result,
            subject=subject,
            html=html,
            from_name=from_name,
            to=[recipient],
            cc=[],
            sent_email_id=next(
                (e.sent_email_id for e in reversed(events) if e.sent_email_id is not None), None
            ),
            user_contact_id=thread.user_contact_id,
            now=sent_at,
        )
        await expire_thread_proposals(db, mailbox.id, thread.thread_id, sent_at)
        await apply_sync_transition(
            db,
            user_contact_id=thread.user_contact_id,
            direction=Direction.OUTBOUND,
            from_address=mailbox.email,
            sent_at=sent_at,
            now=sent_at,
        )
        await db.commit()
        message_id = await db.scalar(
            select(EmailEvent.id).where(
                EmailEvent.provider == mailbox.provider,
                EmailEvent.provider_message_id == result.provider_message_id,
            )
        )
    except Exception:
        await db.rollback()
        logger.exception(
            "Reply in thread %s was sent but not recorded",
            thread.thread_id,
            extra={"user_id": user_id, "mailbox_id": mailbox.id},
        )

    logger.info(
        "Sent a reply from the inbox in thread %s",
        thread.thread_id,
        extra={"user_id": user_id, "mailbox_id": mailbox.id},
    )
    return MessageOut(
        id=str(message_id) if message_id is not None else result.provider_message_id,
        sender="me",
        body=text,
        sent_at=sent_at,
    )
