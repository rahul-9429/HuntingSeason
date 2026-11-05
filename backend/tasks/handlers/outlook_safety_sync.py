from datetime import datetime, timedelta, timezone
from typing import Any

from models.enums import MailboxProvider, MailboxStatus
from services import mailbox_manager
from services.email_event.adapters import microsoft_adapter
from services.email_event.email_processor import EmailEventProcessor
from services.email_providers.microsoft_provider import MicrosoftProvider
from services.redis import webhooks

OVERLAP = timedelta(minutes=5)
FIRST_LOOKBACK = timedelta(days=1)


async def handle(payload: dict[str, Any]) -> None:
    mailbox_id = int(payload["mailbox_id"])
    mailbox = await mailbox_manager.get(mailbox_id)
    if (
        mailbox is None
        or mailbox.provider != MailboxProvider.MICROSOFT
        or mailbox.status == MailboxStatus.NEEDS_RECONNECT
    ):
        return

    started = datetime.now(timezone.utc)
    since = (await webhooks.last_outlook_safety_sync(mailbox_id) or started - FIRST_LOOKBACK) - OVERLAP
    provider = MicrosoftProvider(mailbox)
    sent_folder_id = await provider.sent_folder_id()
    raw = [
        *await provider.messages_since("Inbox", since),
        *await provider.messages_since("SentItems", since),
    ]
    await EmailEventProcessor().process(
        mailbox,
        [microsoft_adapter.normalize(message, mailbox.email, sent_folder_id) for message in raw],
    )
    await webhooks.set_last_outlook_safety_sync(mailbox_id, started)
