import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import formataddr
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy import Select, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import AsyncSessionLocal
from models.email_template import EmailTemplate
from models.emailed_address import EmailedAddress
from models.enums import Direction, MailboxStatus, OutreachStage, Writer
from models.outreach_settings import OutreachSettings
from models.sent_email import SentEmail
from models.user_contact import UserContact
from services import mailbox_manager
from services.email_event.status_transition import is_mailer_daemon, set_stage
from services.email_event.threads import record_outbound, thread_events, thread_references
from services.email_providers.email_provider import (
    MailboxAuthError,
    ProviderConfigError,
    SendResult,
    get_email_provider,
)
from services.email_providers.utils import build_quote_text
from services.errors import ServiceError
from services.outreach import drafting, eligibility, limits, no_response_sweeper, pacing
from services.outreach.country_business_hours import is_country_send_allowed
from services.outreach.drafting import Draft, DraftContext, DraftingError
from services.outreach.eligibility import Lead
from services.outreach.settings import (
    EmailSendSchedule,
    default_template,
    get_email_send_schedule,
    get_settings,
    get_template,
    writer_blocker,
)
from services.outreach.user_info import get_user_info
from services.redis import key, locks

logger = logging.getLogger(__name__)

USER_LOCK_TTL = 15 * 60
CONTACT_LOCK_TTL = 300
PAGE_SIZE = 10


class _Outcome(Enum):
    SENT = "sent"
    SKIPPED = "skipped"
    LIMIT_REACHED = "limit_reached"


class _StopRun(Exception):
    pass


SEND_ANYTIME: EmailSendSchedule = {"enabled": False, "overrides": {}}


@dataclass(frozen=True)
class _Thread:
    first_email: SentEmail
    follow_ups: list[SentEmail]
    reply_to_provider_message_id: str
    reply_to_internet_message_id: str
    references: list[str]


async def run(user_id: int, *, scheduled: bool = False) -> None:
    lock_key = key("outreach", "lock", "user", user_id)
    token = await locks.acquire(lock_key, USER_LOCK_TTL)
    if token is None:
        logger.info("Outreach for user %s is already running", user_id, extra={"user_id": user_id})
        return
    try:
        await _run(user_id, scheduled, lambda: locks.extend(lock_key, token, USER_LOCK_TTL))
    finally:
        await locks.release(lock_key, token)


async def _run(user_id: int, scheduled: bool, keep_lock: Callable[[], Awaitable[bool]]) -> None:
    async with AsyncSessionLocal() as db:
        settings = await get_settings(db, user_id)
        mailbox = await mailbox_manager.get_for_user(db, user_id)
        user_info = await get_user_info(db, user_id)
        template = await default_template(db, user_id)
        schedule = await get_email_send_schedule(db, user_id)

    skip = None
    if scheduled and not settings.enabled:
        skip = "outreach is turned off"
    elif mailbox is None or mailbox.status != MailboxStatus.ACTIVE:
        skip = "no active mailbox"
    else:
        skip = writer_blocker(settings, template, user_info)
    now = datetime.now(timezone.utc)
    if skip or mailbox is None:
        logger.info("Skipping outreach for user %s: %s", user_id, skip, extra={"user_id": user_id})
        return

    if not pacing.is_due(mailbox.next_send_at, now):
        logger.info(
            "Mailbox %s is between sends until %s",
            mailbox.id,
            mailbox.next_send_at,
            extra={"user_id": user_id, "mailbox_id": mailbox.id},
        )
        return

    outreach = _OutreachRun(
        user_id,
        DraftContext(settings, mailbox, user_info, template),
        keep_lock,
        stop_when_disabled=settings.enabled,
        schedule=schedule,
        paced=True,
    )
    try:
        await outreach.first_touches()
        await outreach.follow_ups()
    except _StopRun as exc:
        logger.warning(
            "Stopped outreach for user %s: %s",
            user_id,
            exc,
            extra={"user_id": user_id, "mailbox_id": mailbox.id},
        )
    if not outreach.sent_this_run:
        await _hold_if_the_day_is_spent(user_id, mailbox.id, outreach.cap)
    gone_quiet = await no_response_sweeper.sweep(user_id, settings, datetime.now(timezone.utc))
    logger.info(
        "Outreach for user %s: %d first emails, %d follow-ups, %d with no response, "
        "%d held for local business hours",
        user_id,
        outreach.first_sent,
        outreach.follow_ups_sent,
        gone_quiet,
        outreach.skipped_by_schedule,
        extra={
            "user_id": user_id,
            "first_emails": outreach.first_sent,
            "follow_ups": outreach.follow_ups_sent,
            "no_response": gone_quiet,
            "skipped_by_schedule": outreach.skipped_by_schedule,
        },
    )


async def _hold_if_the_day_is_spent(user_id: int, mailbox_id: int, cap: int) -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        used = await limits.sends_today(db, user_id)
    if used >= cap:
        await pacing.hold_until(mailbox_id, pacing.next_utc_day(now))


class _OutreachRun:
    def __init__(
        self,
        user_id: int,
        ctx: DraftContext,
        keep_lock: Callable[[], Awaitable[bool]],
        *,
        stop_when_disabled: bool,
        schedule: EmailSendSchedule,
        paced: bool,
    ):
        self.user_id = user_id
        self.ctx = ctx
        self.keep_lock = keep_lock
        self.stop_when_disabled = stop_when_disabled
        self.schedule = schedule
        self.paced = paced
        self.sent_this_run = False
        self.skipped_by_schedule = 0
        self.mailbox = ctx.mailbox
        self.own_domain = eligibility.mailbox_domain(ctx.mailbox.email)
        self.started = datetime.now(timezone.utc)
        self.cap = limits.daily_cap(ctx.mailbox.warmup_started_at, self.started)
        self.provider = get_email_provider(ctx.mailbox)
        self.first_sent = 0
        self.follow_ups_sent = 0

    def _first_touch_query(self) -> Select[Any]:
        return eligibility.first_touch_query(self.user_id, self.own_domain)

    def _follow_up_query(self) -> Select[Any]:
        return eligibility.follow_up_query(
            self.user_id, self.own_domain, self.ctx.settings, self.started
        )

    def _held_for_local_hours(self, lead: Lead) -> bool:
        if not self.schedule["enabled"]:
            return False
        return not is_country_send_allowed(
            lead.contact.country, self.schedule["overrides"], datetime.now(timezone.utc)
        )

    def _spent(self) -> bool:
        return self.paced and self.sent_this_run

    async def _check_can_continue(self) -> None:
        if not await self.keep_lock():
            raise _StopRun("the run lock expired")
        if self.stop_when_disabled:
            async with AsyncSessionLocal() as db:
                enabled = await db.scalar(
                    select(OutreachSettings.enabled).where(OutreachSettings.user_id == self.user_id)
                )
            if not enabled:
                raise _StopRun("outreach was turned off")

    async def first_touches(self) -> None:
        if self._spent():
            return
        async with AsyncSessionLocal() as db:
            follow_ups_due = await eligibility.any_match(db, self._follow_up_query())
        after: Optional[tuple[datetime, int]] = None
        while True:
            async with AsyncSessionLocal() as db:
                page = await eligibility.first_touch_page(
                    db, self.user_id, self.own_domain, after, PAGE_SIZE
                )
            if not page:
                return
            for lead in page:
                await self._check_can_continue()
                after = (lead.user_contact.found_at, lead.user_contact.id)
                if self._held_for_local_hours(lead):
                    self.skipped_by_schedule += 1
                    continue
                outcome = await self._first_touch(lead.user_contact.id, follow_ups_due)
                if outcome is _Outcome.LIMIT_REACHED:
                    logger.info(
                        "User %s reached today's limit for first emails",
                        self.user_id,
                        extra={"user_id": self.user_id, "daily_cap": self.cap},
                    )
                    return
                if outcome is _Outcome.SENT:
                    self.first_sent += 1
                    if self._spent():
                        return

    async def _first_touch(self, user_contact_id: int, follow_ups_due: bool) -> _Outcome:
        lock_key = key("outreach", "lock", "contact", user_contact_id)
        async with locks.lock(lock_key, CONTACT_LOCK_TTL) as acquired:
            if not acquired:
                return _Outcome.SKIPPED
            async with AsyncSessionLocal() as db:
                lead = await eligibility.one(db, self._first_touch_query(), user_contact_id)
                if lead is None:
                    return _Outcome.SKIPPED
                day = await limits.reserve_first_touch(db, self.user_id, self.cap, follow_ups_due)
                if day is None:
                    return _Outcome.LIMIT_REACHED

            draft = await self._draft(
                lambda: drafting.first_touch(self.ctx, lead), lead, day, follow_up=False
            )
            if draft is None:
                return _Outcome.SKIPPED
            result = await self._send(
                lambda: self.provider.send_email(
                    to=lead.email, subject=draft.subject, html=draft.html, from_name=draft.from_name
                ),
                lead,
                day,
                follow_up=False,
            )
            if result is None:
                return _Outcome.SKIPPED
            await self._record(lead, draft, result, attempt=0)
            return _Outcome.SENT

    async def send_written(self, user_contact_id: int, draft: Draft) -> None:
        lock_key = key("outreach", "lock", "contact", user_contact_id)
        async with locks.lock(lock_key, CONTACT_LOCK_TTL) as acquired:
            if not acquired:
                raise ServiceError("This person is being emailed right now", status_code=409)
            async with AsyncSessionLocal() as db:
                lead = await eligibility.one(db, self._first_touch_query(), user_contact_id)
                if lead is None:
                    raise ServiceError(
                        "This person can't get a first email: they were emailed before, "
                        "replied, or their address bounced",
                        status_code=409,
                    )
                day = await limits.reserve_first_touch(
                    db, self.user_id, self.cap, follow_ups_due=False
                )
                if day is None:
                    raise ServiceError("Today's sending limit is used up", status_code=429)

            try:
                result = await self.provider.send_email(
                    to=lead.email, subject=draft.subject, html=draft.html, from_name=draft.from_name
                )
            except Exception as exc:
                await self._release(day, follow_up=False)
                self._log_skip(lead, "the send failed", exc)
                if isinstance(exc, ProviderConfigError):
                    raise ServiceError(
                        "This mail provider isn't set up on the server", status_code=503
                    ) from exc
                if isinstance(exc, MailboxAuthError):
                    raise ServiceError(str(exc), status_code=409) from exc
                raise ServiceError("Couldn't send the email. Try again.", status_code=502) from exc
            await self._record(lead, draft, result, attempt=0)

    async def follow_ups(self) -> None:
        if self._spent():
            return
        async with AsyncSessionLocal() as db:
            new_leads_waiting = await eligibility.any_match(db, self._first_touch_query())
        after: Optional[tuple[datetime, int]] = None
        while True:
            async with AsyncSessionLocal() as db:
                page = await eligibility.follow_up_page(
                    db, self.user_id, self.own_domain, self.ctx.settings, self.started, after, PAGE_SIZE
                )
            if not page:
                return
            for lead in page:
                await self._check_can_continue()
                after = (lead.user_contact.last_contacted_at or self.started, lead.user_contact.id)
                if self._held_for_local_hours(lead):
                    self.skipped_by_schedule += 1
                    continue
                outcome = await self._follow_up(lead.user_contact.id, new_leads_waiting)
                if outcome is _Outcome.LIMIT_REACHED:
                    logger.info(
                        "User %s reached today's limit for follow-ups",
                        self.user_id,
                        extra={"user_id": self.user_id, "daily_cap": self.cap},
                    )
                    return
                if outcome is _Outcome.SENT:
                    self.follow_ups_sent += 1
                    if self._spent():
                        return

    async def _follow_up(self, user_contact_id: int, new_leads_waiting: bool) -> _Outcome:
        lock_key = key("outreach", "lock", "contact", user_contact_id)
        async with locks.lock(lock_key, CONTACT_LOCK_TTL) as acquired:
            if not acquired:
                return _Outcome.SKIPPED
            async with AsyncSessionLocal() as db:
                lead = await eligibility.one(db, self._follow_up_query(), user_contact_id)
                if lead is None:
                    return _Outcome.SKIPPED
                thread = await self._thread(db, lead)
                if thread is None:
                    self._log_skip(lead, "its first email wasn't sent from this mailbox", None)
                    return _Outcome.SKIPPED
                template = await get_template(db, self.user_id, thread.first_email.template_id)
                day = await limits.reserve_follow_up(db, self.user_id, self.cap, new_leads_waiting)
                if day is None:
                    return _Outcome.LIMIT_REACHED

            attempt = lead.user_contact.follow_up_count + 1
            draft = await self._draft(
                lambda: drafting.follow_up(
                    self.ctx, lead, thread.first_email, thread.follow_ups, attempt, template
                ),
                lead,
                day,
                follow_up=True,
            )
            if draft is None:
                return _Outcome.SKIPPED
            previous = thread.follow_ups[-1] if thread.follow_ups else thread.first_email
            result = await self._send(
                lambda: self.provider.send_reply(
                    reply_to_provider_message_id=thread.reply_to_provider_message_id,
                    reply_to_internet_message_id=thread.reply_to_internet_message_id,
                    references=thread.references,
                    thread_id=thread.first_email.thread_id,
                    to=lead.email,
                    subject=draft.subject,
                    html=draft.html,
                    from_name=draft.from_name,
                    quote_text=build_quote_text(
                        previous.body_html,
                        formataddr((draft.from_name, self.mailbox.email)),
                        previous.sent_at,
                    ),
                ),
                lead,
                day,
                follow_up=True,
            )
            if result is None:
                return _Outcome.SKIPPED
            await self._record(lead, draft, result, attempt=attempt)
            return _Outcome.SENT

    async def _thread(self, db: AsyncSession, lead: Lead) -> Optional[_Thread]:
        first_email = await db.scalar(
            select(SentEmail)
            .where(
                SentEmail.user_contact_id == lead.user_contact.id,
                SentEmail.mailbox_id == self.mailbox.id,
                SentEmail.follow_up_attempt == 0,
            )
            .order_by(SentEmail.sent_at.desc())
            .limit(1)
        )
        if first_email is None:
            return None
        follow_ups = list(
            (
                await db.scalars(
                    select(SentEmail)
                    .where(
                        SentEmail.mailbox_id == self.mailbox.id,
                        SentEmail.thread_id == first_email.thread_id,
                        SentEmail.follow_up_attempt > 0,
                    )
                    .order_by(SentEmail.sent_at, SentEmail.id)
                )
            ).all()
        )
        events = await thread_events(db, self.mailbox.id, first_email.thread_id)
        latest_human = next(
            (
                event
                for event in reversed(events)
                if event.direction == Direction.OUTBOUND or not is_mailer_daemon(event.from_address)
            ),
            None,
        )
        latest = latest_human or (follow_ups[-1] if follow_ups else first_email)
        references = thread_references(events) or [
            email.internet_message_id
            for email in (first_email, *follow_ups)
            if email.internet_message_id
        ]
        return _Thread(
            first_email=first_email,
            follow_ups=follow_ups,
            reply_to_provider_message_id=latest.provider_message_id,
            reply_to_internet_message_id=latest.internet_message_id or "",
            references=references,
        )

    async def _draft(
        self, write: Callable[[], Awaitable[Draft]], lead: Lead, day: date, *, follow_up: bool
    ) -> Optional[Draft]:
        try:
            return await write()
        except Exception as exc:
            await self._release(day, follow_up=follow_up)
            if isinstance(exc, DraftingError):
                self._log_skip(lead, "couldn't write the email", exc)
            else:
                logger.exception(
                    "Drafting for contact %s failed",
                    lead.user_contact.id,
                    extra={"user_id": self.user_id, "user_contact_id": lead.user_contact.id},
                )
            return None

    async def _send(
        self,
        send: Callable[[], Awaitable[SendResult]],
        lead: Lead,
        day: date,
        *,
        follow_up: bool,
    ) -> Optional[SendResult]:
        try:
            return await send()
        except (MailboxAuthError, ProviderConfigError) as exc:
            await self._release(day, follow_up=follow_up)
            raise _StopRun(str(exc)) from exc
        except Exception as exc:
            await self._release(day, follow_up=follow_up)
            self._log_skip(lead, "the send failed", exc)
            return None

    async def _release(self, day: date, *, follow_up: bool) -> None:
        async with AsyncSessionLocal() as db:
            await limits.release(db, self.user_id, day, follow_up=follow_up)

    async def _record(self, lead: Lead, draft: Draft, result: SendResult, attempt: int) -> None:
        self.sent_this_run = True
        await asyncio.shield(self._save_send(lead, draft, result, attempt))
        await pacing.hold_for_gap(
            self.mailbox.id, self.ctx.settings, datetime.now(timezone.utc)
        )

    async def _save_send(self, lead: Lead, draft: Draft, result: SendResult, attempt: int) -> None:
        for try_number in (1, 2):
            now = datetime.now(timezone.utc)
            try:
                async with AsyncSessionLocal() as db:
                    sent = SentEmail(
                        user_id=self.user_id,
                        mailbox_id=self.mailbox.id,
                        provider=self.mailbox.provider,
                        provider_message_id=result.provider_message_id,
                        thread_id=result.thread_id,
                        subject=draft.subject,
                        body_html=draft.html,
                        internet_message_id=result.internet_message_id or None,
                        user_contact_id=lead.user_contact.id,
                        user_company_id=lead.user_contact.user_company_id,
                        template_id=draft.template_id,
                        writer=draft.writer,
                        follow_up_attempt=attempt,
                    )
                    db.add(sent)
                    await db.flush()
                    await record_outbound(
                        db,
                        mailbox=self.mailbox,
                        result=result,
                        subject=draft.subject,
                        html=draft.html,
                        from_name=draft.from_name,
                        to=[lead.email],
                        cc=[],
                        sent_email_id=sent.id,
                        user_contact_id=lead.user_contact.id,
                        now=now,
                    )
                    contact = await db.get(UserContact, lead.user_contact.id, with_for_update=True)
                    if contact is not None:
                        if attempt == 0:
                            set_stage(contact, OutreachStage.CONTACTED, now)
                            contact.first_contacted_at = contact.first_contacted_at or now
                        else:
                            contact.follow_up_count += 1
                        contact.last_contacted_at = now
                    if attempt == 0:
                        await db.execute(
                            pg_insert(EmailedAddress)
                            .values(user_id=self.user_id, email=lead.email.lower())
                            .on_conflict_do_nothing(index_elements=["user_id", "email"])
                        )
                    await db.commit()
                return
            except Exception:
                logger.exception(
                    "Couldn't record the email to contact %s (try %d)",
                    lead.user_contact.id,
                    try_number,
                    extra={"user_id": self.user_id, "user_contact_id": lead.user_contact.id},
                )
        logger.error(
            "Email %s to contact %s was sent but isn't recorded; they may be emailed again",
            result.provider_message_id,
            lead.user_contact.id,
            extra={
                "user_id": self.user_id,
                "user_contact_id": lead.user_contact.id,
                "provider_message_id": result.provider_message_id,
            },
        )

    def _log_skip(self, lead: Lead, why: str, exc: Optional[Exception]) -> None:
        logger.warning(
            "Skipped contact %s: %s%s",
            lead.user_contact.id,
            why,
            f" ({exc})" if exc else "",
            extra={"user_id": self.user_id, "user_contact_id": lead.user_contact.id},
        )


async def _keep_going() -> bool:
    return True


async def send_written(
    user_id: int,
    user_contact_id: int,
    subject: str,
    html: str,
    writer: Optional[Writer],
    template_id: Optional[int],
) -> None:
    async with AsyncSessionLocal() as db:
        settings = await get_settings(db, user_id)
        mailbox = await mailbox_manager.get_for_user(db, user_id)
        user_info = await get_user_info(db, user_id)
        template = await get_template(db, user_id, template_id)
    if mailbox is None:
        raise ServiceError("Connect your mailbox first", status_code=409)
    if mailbox.status != MailboxStatus.ACTIVE:
        raise ServiceError("Reconnect your mailbox to send", status_code=409)

    ctx = DraftContext(settings, mailbox, user_info, template)
    draft = Draft(
        subject=subject,
        html=html,
        writer=writer or settings.writer,
        template_id=template.id if template else None,
        from_name=drafting.sender_name(ctx, template),
    )
    outreach = _OutreachRun(
        user_id, ctx, _keep_going, stop_when_disabled=False, schedule=SEND_ANYTIME, paced=False
    )
    await outreach.send_written(user_contact_id, draft)


async def preview(
    db: AsyncSession,
    user_id: int,
    user_contact_id: int,
    writer: Optional[Writer],
    template_id: Optional[int] = None,
) -> Optional[Draft]:
    settings = await get_settings(db, user_id)
    mailbox = await mailbox_manager.get_for_user(db, user_id)
    if mailbox is None:
        raise DraftingError("Connect a mailbox first")
    lead = await eligibility.one(db, eligibility.leads_with_email(user_id), user_contact_id)
    if lead is None:
        return None
    template: Optional[EmailTemplate]
    if template_id is None:
        template = await default_template(db, user_id)
    else:
        template = await get_template(db, user_id, template_id)
        if template is None:
            raise DraftingError("That template doesn't exist")
    ctx = DraftContext(settings, mailbox, await get_user_info(db, user_id), template)
    return await drafting.first_touch(ctx, lead, writer)
