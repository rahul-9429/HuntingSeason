import asyncio
import logging
from typing import Any

from db.session import AsyncSessionLocal
from models.enums import MailboxProvider, MailboxStatus
from models.mailbox import Mailbox
from services import mailbox_manager
from services.email_event.adapters import gmail_adapter
from services.email_event.email_processor import EmailEventProcessor
from services.email_event.threads import our_threads
from services.email_providers.email_provider import NotFoundError
from services.email_providers.gmail_provider import GmailProvider
from services.redis import webhooks

logger = logging.getLogger(__name__)

BATCH_DELAY_SECONDS = 20
RESYNC_QUERY = "newer_than:7d"


async def handle(payload: dict[str, Any]) -> None:
    mailbox_id = int(payload["mailbox_id"])
    if payload.get("batch", True):
        await asyncio.sleep(BATCH_DELAY_SECONDS)
    await webhooks.release_gmail_sync(mailbox_id)

    mailbox = await mailbox_manager.get(mailbox_id)
    if (
        mailbox is None
        or mailbox.provider != MailboxProvider.GMAIL
        or mailbox.status == MailboxStatus.NEEDS_RECONNECT
    ):
        return
    provider = GmailProvider(mailbox)

    if mailbox.gmail_history_id is None:
        await _resync(mailbox, provider, "it has no sync cursor yet")
        return
    try:
        message_ids, cursor = await provider.history_message_ids(mailbox.gmail_history_id)
    except NotFoundError:
        await _resync(mailbox, provider, "its sync cursor is too old")
        return
    await _process(mailbox, provider, message_ids)
    await mailbox_manager.save_gmail_cursor(mailbox_id, cursor)


async def _resync(mailbox: Mailbox, provider: GmailProvider, why: str) -> None:
    logger.warning(
        "Resyncing the last 7 days of Gmail mailbox %s: %s",
        mailbox.id,
        why,
        extra={"mailbox_id": mailbox.id, "user_id": mailbox.user_id},
    )
    cursor = await provider.profile_history_id()
    await _process(mailbox, provider, await provider.recent_message_ids(RESYNC_QUERY))
    await mailbox_manager.save_gmail_cursor(mailbox.id, cursor, force=True)


async def _process(mailbox: Mailbox, provider: GmailProvider, message_ids: dict[str, str]) -> None:
    async with AsyncSessionLocal() as db:
        threads = await our_threads(db, mailbox.id, message_ids.values())
    messages = []
    for message_id, thread_id in message_ids.items():
        if thread_id not in threads:
            continue
        try:
            raw = await provider.get_message(message_id)
        except NotFoundError:
            continue
        if not gmail_adapter.is_draft(raw):
            messages.append(gmail_adapter.normalize(raw, mailbox.email))
    if messages:
        await EmailEventProcessor().process(mailbox, messages)
