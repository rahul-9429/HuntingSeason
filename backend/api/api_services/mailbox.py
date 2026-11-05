import asyncio
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from email.utils import formataddr
from typing import Any, Optional
from urllib.parse import parse_qs, urlsplit

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services.errors import ServiceError
from api.type_models.mailbox import ConnectRequest, MailboxOut, TestSendRequest
from models.enums import MailboxProvider
from models.mailbox import Mailbox
from models.sent_email import SentEmail
from services import mailbox_manager
from services.email_event import subscriptions
from services.email_event.threads import record_outbound, thread_events, thread_references
from services.email_providers import gmail_provider, microsoft_provider
from services.email_providers.email_provider import (
    EmailProviderError,
    MailboxAuthError,
    ProviderConfigError,
    SendResult,
    get_email_provider,
)
from services.email_providers.utils import build_quote_text, sanitize_email_html
from services.outreach import deliverability, limits
from services.redis import get_redis, key

logger = logging.getLogger(__name__)

STATE_TTL_SECONDS = 600


def _check_redirect_uri(redirect_uri: str) -> None:
    web = urlsplit(os.getenv("WEB_URL", "http://localhost:3000"))
    target = urlsplit(redirect_uri)
    base_path = web.path.rstrip("/")
    same_origin = (target.scheme, target.netloc.lower()) == (web.scheme, web.netloc.lower())
    if not same_origin or not (target.path == base_path or target.path.startswith(f"{base_path}/")):
        raise ServiceError("redirect_uri must be a page of WEB_URL", status_code=400)


def _not_configured(exc: ProviderConfigError) -> ServiceError:
    logger.error("Mailbox provider not configured: %s", exc)
    return ServiceError("This mail provider isn't set up on the server", status_code=503)


async def auth_url(user_id: int, provider: MailboxProvider, redirect_uri: str) -> str:
    _check_redirect_uri(redirect_uri)
    state = secrets.token_urlsafe(24)
    record: dict[str, Any] = {
        "user_id": user_id,
        "provider": provider.value,
        "redirect_uri": redirect_uri,
    }
    try:
        if provider == MailboxProvider.GMAIL:
            flow = Flow.from_client_config(
                gmail_provider.client_config(),
                gmail_provider.SCOPES,
                redirect_uri=redirect_uri,
                autogenerate_code_verifier=True,
            )
            url, _ = flow.authorization_url(access_type="offline", prompt="consent", state=state)
            record["code_verifier"] = flow.code_verifier
        else:
            app = await asyncio.to_thread(microsoft_provider.msal_app)
            url = app.get_authorization_request_url(
                microsoft_provider.SCOPES, redirect_uri=redirect_uri, state=state, prompt="consent"
            )
    except ProviderConfigError as exc:
        raise _not_configured(exc) from exc

    await get_redis().set(key("oauth_state", state), json.dumps(record), ex=STATE_TTL_SECONDS)
    return str(url)


async def _exchange_google(
    code: str, redirect_uri: str, code_verifier: Optional[str]
) -> tuple[str, Optional[str], dict[str, Any]]:
    flow = Flow.from_client_config(
        gmail_provider.client_config(),
        gmail_provider.SCOPES,
        redirect_uri=redirect_uri,
        code_verifier=code_verifier,
    )

    def exchange() -> tuple[Any, dict[str, Any]]:
        flow.fetch_token(code=code)
        profile = (
            build("oauth2", "v2", credentials=flow.credentials, cache_discovery=False)
            .userinfo()
            .get()
            .execute()
        )
        return flow.credentials, profile

    try:
        credentials, profile = await asyncio.to_thread(exchange)
    except Exception as exc:
        logger.warning("Google code exchange failed: %s", exc)
        raise ServiceError(
            "Couldn't connect Gmail. Start again and allow every permission it asks for.",
            status_code=400,
        ) from exc

    email = profile.get("email")
    if not email:
        raise ServiceError("Google didn't share the account's email address", status_code=400)
    if not credentials.refresh_token:
        raise ServiceError("Google didn't return a refresh token. Start again.", status_code=400)
    return email, profile.get("name"), gmail_provider.credentials_to_dict(credentials)


async def _exchange_microsoft(
    code: str, redirect_uri: str
) -> tuple[str, Optional[str], dict[str, Any]]:
    failed = ServiceError("Couldn't connect Outlook. Start again.", status_code=400)
    try:
        app = await asyncio.to_thread(microsoft_provider.msal_app)
        result = await asyncio.to_thread(
            app.acquire_token_by_authorization_code,
            code,
            microsoft_provider.SCOPES,
            redirect_uri=redirect_uri,
        )
    except OSError as exc:
        logger.warning("Microsoft code exchange failed: %s", exc)
        raise failed from exc
    if "access_token" not in result or not result.get("refresh_token"):
        logger.warning(
            "Microsoft code exchange failed: %s %s",
            result.get("error"),
            result.get("error_description"),
            extra={"msal_error": result.get("error")},
        )
        raise failed

    try:
        me = await microsoft_provider.get_me(result["access_token"])
    except EmailProviderError as exc:
        raise failed from exc
    email = me.get("mail") or me.get("userPrincipalName")
    if not email:
        raise ServiceError("Microsoft didn't share the account's email address", status_code=400)
    return email, me.get("displayName"), microsoft_provider.credentials_from_token_result(result)


async def connect(db: AsyncSession, user_id: int, req: ConnectRequest) -> MailboxOut:
    query = parse_qs(urlsplit(req.url).query)
    state = (query.get("state") or [""])[0]
    raw = await get_redis().getdel(key("oauth_state", state)) if state else None
    record = json.loads(raw) if raw else None
    if (
        not isinstance(record, dict)
        or record.get("user_id") != user_id
        or record.get("provider") != req.provider.value
        or record.get("redirect_uri") != req.redirect_uri
    ):
        raise ServiceError("This sign-in link is invalid or has expired. Start again.", status_code=400)

    error = (query.get("error") or [""])[0]
    if error:
        raise ServiceError(f"The provider refused access ({error})", status_code=400)
    code = (query.get("code") or [""])[0]
    if not code:
        raise ServiceError("The redirect URL has no code", status_code=400)

    try:
        if req.provider == MailboxProvider.GMAIL:
            email, name, credentials = await _exchange_google(
                code, req.redirect_uri, record.get("code_verifier")
            )
        else:
            email, name, credentials = await _exchange_microsoft(code, req.redirect_uri)
    except ProviderConfigError as exc:
        raise _not_configured(exc) from exc

    taken = ServiceError("This mailbox is already connected to another account", status_code=409)
    if await mailbox_manager.is_taken(db, email, user_id):
        raise taken
    previous = await mailbox_manager.get_for_user(db, user_id)
    if previous is not None and (
        previous.provider != req.provider or previous.email.lower() != email.lower()
    ):
        await subscriptions.teardown(previous)
    try:
        mailbox = await mailbox_manager.connect(
            db,
            user_id=user_id,
            provider=req.provider,
            email=email,
            from_name=name,
            credentials=credentials,
        )
    except mailbox_manager.MailboxTakenError as exc:
        raise taken from exc
    await subscriptions.setup(mailbox)
    return await _to_out(db, mailbox)


async def _to_out(db: AsyncSession, mailbox: Mailbox) -> MailboxOut:
    now = datetime.now(timezone.utc)
    return MailboxOut(
        provider=mailbox.provider,
        email=mailbox.email,
        from_name=mailbox.from_name,
        status=mailbox.status,
        warmup_day=limits.warmup_days(mailbox.warmup_started_at, now) + 1,
        daily_cap=limits.daily_cap(mailbox.warmup_started_at, now),
        sends_today=await limits.sends_today(db, mailbox.user_id),
        bounce_rate_7d=await deliverability.bounce_rate(db, mailbox.id, now),
    )


async def _require_mailbox(db: AsyncSession, user_id: int) -> Mailbox:
    mailbox = await mailbox_manager.get_for_user(db, user_id)
    if mailbox is None:
        raise ServiceError("No mailbox connected", status_code=404)
    return mailbox


async def get(db: AsyncSession, user_id: int) -> MailboxOut:
    return await _to_out(db, await _require_mailbox(db, user_id))


async def delete(db: AsyncSession, user_id: int) -> None:
    mailbox = await mailbox_manager.get_for_user(db, user_id)
    if mailbox is not None:
        await subscriptions.teardown(mailbox)
    await mailbox_manager.delete_for_user(db, user_id)


async def test_send(db: AsyncSession, user_id: int, req: TestSendRequest) -> SentEmail:
    mailbox = await _require_mailbox(db, user_id)
    html = sanitize_email_html(req.body_html)
    previous: Optional[SentEmail] = None
    if req.reply_to_sent_email_id is not None:
        previous = await db.scalar(
            select(SentEmail).where(
                SentEmail.id == req.reply_to_sent_email_id,
                SentEmail.user_id == user_id,
                SentEmail.mailbox_id == mailbox.id,
            )
        )
        if previous is None:
            raise ServiceError("No email with that id was sent from this mailbox", status_code=404)

    try:
        provider = get_email_provider(mailbox)
        result: SendResult
        if previous is None:
            result = await provider.send_email(
                to=req.to, subject=req.subject, html=html, from_name=mailbox.from_name
            )
        else:
            events = await thread_events(db, mailbox.id, previous.thread_id)
            references = thread_references(events) or [
                previous.internet_message_id or ""
            ]
            result = await provider.send_reply(
                reply_to_provider_message_id=previous.provider_message_id,
                reply_to_internet_message_id=previous.internet_message_id or "",
                references=[ref for ref in references if ref],
                thread_id=previous.thread_id,
                to=req.to,
                subject=req.subject,
                html=html,
                from_name=mailbox.from_name,
                quote_text=build_quote_text(
                    previous.body_html,
                    formataddr((mailbox.from_name, mailbox.email)),
                    previous.sent_at,
                ),
            )
    except ProviderConfigError as exc:
        raise _not_configured(exc) from exc
    except MailboxAuthError as exc:
        raise ServiceError(str(exc), status_code=409) from exc
    except EmailProviderError as exc:
        logger.warning(
            "Test send failed for mailbox %s: %s",
            mailbox.id,
            exc,
            extra={"user_id": user_id, "mailbox_id": mailbox.id},
        )
        raise ServiceError(str(exc), status_code=502) from exc

    sent = SentEmail(
        user_id=user_id,
        mailbox_id=mailbox.id,
        provider=mailbox.provider,
        provider_message_id=result.provider_message_id,
        internet_message_id=result.internet_message_id or None,
        thread_id=result.thread_id,
        subject=req.subject,
        body_html=html,
        follow_up_attempt=previous.follow_up_attempt + 1 if previous else 0,
    )
    db.add(sent)
    await db.flush()
    await record_outbound(
        db,
        mailbox=mailbox,
        result=result,
        subject=req.subject,
        html=html,
        from_name=mailbox.from_name,
        to=[req.to],
        cc=[],
        sent_email_id=sent.id,
        user_contact_id=None,
        now=datetime.now(timezone.utc),
    )
    await db.commit()
    logger.info(
        "Test email %s sent from mailbox %s",
        sent.id,
        mailbox.id,
        extra={"user_id": user_id, "mailbox_id": mailbox.id, "sent_email_id": sent.id},
    )
    return sent
