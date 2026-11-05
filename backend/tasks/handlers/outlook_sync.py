import asyncio
import logging
from typing import Any

from models.enums import MailboxProvider, MailboxStatus
from services import mailbox_manager
from services.email_event.adapters import microsoft_adapter
from services.email_event.email_processor import EmailEventProcessor, EventProcessingError
from services.email_providers.email_provider import (
    EmailProviderError,
    MailboxAuthError,
    NotFoundError,
)
from services.email_providers.microsoft_provider import MicrosoftProvider
from services.redis import push_task, webhooks

logger = logging.getLogger(__name__)

BATCH_DELAY_SECONDS = 20


async def handle(payload: dict[str, Any]) -> None:
    mailbox_id = int(payload["mailbox_id"])
    await asyncio.sleep(BATCH_DELAY_SECONDS)
    await webhooks.release_outlook_sync(mailbox_id)

    mailbox = await mailbox_manager.get(mailbox_id)
    if (
        mailbox is None
        or mailbox.provider != MailboxProvider.MICROSOFT
        or mailbox.status == MailboxStatus.NEEDS_RECONNECT
    ):
        return
    message_ids = await webhooks.take_outlook_pending(mailbox_id)
    if not message_ids:
        return

    provider = MicrosoftProvider(mailbox)
    sent_folder_id = await provider.sent_folder_id()
    messages = []
    retry: list[str] = []
    for index, message_id in enumerate(message_ids):
        try:
            raw = await provider.get_message(message_id)
        except NotFoundError:
            continue
        except MailboxAuthError:
            retry.extend(message_ids[index:])
            break
        except EmailProviderError as exc:
            logger.warning(
                "Couldn't read Outlook message %s: %s",
                message_id,
                exc,
                extra={"mailbox_id": mailbox_id, "status_code": exc.status_code},
            )
            if exc.retryable:
                retry.append(message_id)
            continue
        messages.append(microsoft_adapter.normalize(raw, mailbox.email, sent_folder_id))

    try:
        if messages:
            await EmailEventProcessor().process(mailbox, messages)
    except EventProcessingError as exc:
        retry.extend(exc.failed)
    await webhooks.finish_outlook_pending(mailbox_id)

    if retry:
        await webhooks.add_outlook_pending(mailbox_id, retry)
        if mailbox.status == MailboxStatus.ACTIVE and await webhooks.claim_outlook_sync(mailbox_id):
            await push_task("outlook_sync", {"mailbox_id": mailbox_id})
