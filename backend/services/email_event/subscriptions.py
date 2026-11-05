import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from models.enums import MailboxProvider
from models.mailbox import Mailbox
from services import mailbox_manager
from services.email_providers.email_provider import EmailProviderError, ProviderConfigError
from services.email_providers.gmail_provider import GmailProvider, pubsub_topic
from services.email_providers.microsoft_provider import MicrosoftProvider

logger = logging.getLogger(__name__)

OUTLOOK_FOLDERS = {
    "inbox": "me/mailFolders('Inbox')/messages",
    "sent": "me/mailFolders('SentItems')/messages",
}
OUTLOOK_LIFETIME = timedelta(hours=70)
RENEW_WITHIN = timedelta(hours=12)


def _log_failure(action: str, mailbox: Mailbox, exc: Exception) -> None:
    logger.warning(
        "Couldn't %s for mailbox %s: %s",
        action,
        mailbox.id,
        exc,
        extra={"mailbox_id": mailbox.id, "user_id": mailbox.user_id},
    )


async def setup(mailbox: Mailbox) -> None:
    try:
        if mailbox.provider == MailboxProvider.GMAIL:
            await start_gmail_watch(mailbox)
        else:
            await recreate_outlook_subscriptions(mailbox)
    except Exception as exc:
        _log_failure("start inbound sync", mailbox, exc)


async def teardown(mailbox: Mailbox) -> None:
    try:
        if mailbox.provider == MailboxProvider.GMAIL:
            await GmailProvider(mailbox).stop_watch()
        else:
            provider = MicrosoftProvider(mailbox)
            for subscription in (mailbox.outlook_subscriptions or {}).values():
                await provider.delete_subscription(subscription["id"])
    except Exception as exc:
        _log_failure("stop inbound sync", mailbox, exc)


async def start_gmail_watch(mailbox: Mailbox) -> None:
    try:
        topic = pubsub_topic()
    except ProviderConfigError as exc:
        logger.warning("%s; Gmail replies rely on the safety sync", exc)
        return
    history_id, expires_at = await GmailProvider(mailbox).watch(topic)
    await mailbox_manager.save_gmail_watch(mailbox.id, history_id, expires_at)


async def renew_gmail_watch(mailbox: Mailbox) -> None:
    expires_at = mailbox.gmail_watch_expires_at
    if expires_at is None or expires_at < datetime.now(timezone.utc) + RENEW_WITHIN:
        await start_gmail_watch(mailbox)


def _notification_url() -> str:
    host = os.getenv("BACKEND_HOST", "").rstrip("/")
    if not host.startswith("https://"):
        raise ProviderConfigError("BACKEND_HOST must be an https URL for Outlook notifications")
    return f"{host}/webhooks/outlook"


async def _create(provider: MicrosoftProvider, resource: str) -> dict[str, Any]:
    expires_at = datetime.now(timezone.utc) + OUTLOOK_LIFETIME
    client_state = secrets.token_urlsafe(24)
    created = await provider.create_subscription(
        resource, _notification_url(), expires_at, client_state
    )
    return {
        "id": created["id"],
        "expires_at": created.get("expirationDateTime") or expires_at.isoformat(),
        "client_state": client_state,
    }


async def recreate_outlook_subscriptions(mailbox: Mailbox) -> None:
    provider = MicrosoftProvider(mailbox)
    for old in (mailbox.outlook_subscriptions or {}).values():
        try:
            await provider.delete_subscription(old["id"])
        except EmailProviderError as exc:
            _log_failure("delete an old Outlook subscription", mailbox, exc)

    subscriptions: dict[str, Any] = {}
    try:
        for folder, resource in OUTLOOK_FOLDERS.items():
            subscriptions[folder] = await _create(provider, resource)
    finally:
        await mailbox_manager.save_outlook_subscriptions(mailbox.id, subscriptions or None)


def _expires_soon(subscription: dict[str, Any], now: datetime) -> bool:
    expires_at = datetime.fromisoformat(str(subscription["expires_at"]).replace("Z", "+00:00"))
    return expires_at < now + RENEW_WITHIN


async def renew_outlook_subscriptions(mailbox: Mailbox) -> None:
    now = datetime.now(timezone.utc)
    provider = MicrosoftProvider(mailbox)
    subscriptions = dict(mailbox.outlook_subscriptions or {})
    changed = False
    for folder, resource in OUTLOOK_FOLDERS.items():
        current = subscriptions.get(folder)
        if current and not _expires_soon(current, now):
            continue
        changed = True
        if current:
            expires_at = now + OUTLOOK_LIFETIME
            try:
                await provider.renew_subscription(current["id"], expires_at)
                subscriptions[folder] = {**current, "expires_at": expires_at.isoformat()}
                continue
            except EmailProviderError as exc:
                _log_failure(f"renew the Outlook {folder} subscription", mailbox, exc)
                try:
                    await provider.delete_subscription(current["id"])
                except EmailProviderError:
                    pass
        try:
            subscriptions[folder] = await _create(provider, resource)
        except (EmailProviderError, ProviderConfigError) as exc:
            _log_failure(f"create the Outlook {folder} subscription", mailbox, exc)
            subscriptions.pop(folder, None)
    if changed:
        await mailbox_manager.save_outlook_subscriptions(mailbox.id, subscriptions or None)
