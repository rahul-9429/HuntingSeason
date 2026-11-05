import base64
import binascii
import json
import logging
import secrets
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import MailboxProvider
from services import mailbox_manager
from services.redis import push_task, webhooks

logger = logging.getLogger(__name__)


async def gmail_push(db: AsyncSession, body: Any) -> None:
    try:
        data = json.loads(base64.b64decode(body["message"]["data"]))
        email = str(data["emailAddress"])
    except (KeyError, TypeError, ValueError, binascii.Error):
        logger.warning("Ignored a malformed Gmail push")
        return

    mailbox = await mailbox_manager.find_by_email(db, email)
    if mailbox is None or mailbox.provider != MailboxProvider.GMAIL:
        return
    if await webhooks.claim_gmail_sync(mailbox.id):
        await push_task("gmail_sync", {"mailbox_id": mailbox.id})


async def outlook_notifications(db: AsyncSession, body: Any) -> None:
    items = body.get("value") if isinstance(body, dict) else None
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or item.get("changeType") != "created":
            continue
        subscription_id = str(item.get("subscriptionId") or "")
        message_id = (item.get("resourceData") or {}).get("id")
        mailbox = (
            await mailbox_manager.find_by_outlook_subscription(db, subscription_id)
            if subscription_id
            else None
        )
        if mailbox is None or not message_id:
            continue
        expected = next(
            (
                str(subscription.get("client_state") or "")
                for subscription in (mailbox.outlook_subscriptions or {}).values()
                if subscription.get("id") == subscription_id
            ),
            "",
        )
        received = str(item.get("clientState") or "")
        if not expected or not secrets.compare_digest(received.encode(), expected.encode()):
            logger.warning(
                "Ignored an Outlook notification with the wrong clientState",
                extra={"mailbox_id": mailbox.id},
            )
            continue
        await webhooks.add_outlook_pending(mailbox.id, [str(message_id)])
        if await webhooks.claim_outlook_sync(mailbox.id):
            await push_task("outlook_sync", {"mailbox_id": mailbox.id})
