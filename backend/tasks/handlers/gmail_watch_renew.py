import logging
from typing import Any

from models.enums import MailboxProvider
from services import mailbox_manager
from services.email_event import subscriptions
from services.email_providers.email_provider import EmailProviderError, ProviderConfigError

logger = logging.getLogger(__name__)


async def handle(payload: dict[str, Any]) -> None:
    for mailbox in await mailbox_manager.active(MailboxProvider.GMAIL):
        try:
            await subscriptions.renew_gmail_watch(mailbox)
        except (EmailProviderError, ProviderConfigError) as exc:
            logger.warning(
                "Couldn't renew the Gmail watch for mailbox %s: %s",
                mailbox.id,
                exc,
                extra={"mailbox_id": mailbox.id},
            )
