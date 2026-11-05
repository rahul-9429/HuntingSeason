from datetime import datetime, timezone
from email.utils import formataddr
from typing import Any, Optional

from models.enums import Direction, MailboxProvider
from services.email_event.types import (
    NormalizedEmailMessage,
    direction_of,
    stored_body,
    text_as_html,
)


def _addresses(recipients: Any) -> list[str]:
    return [
        address.lower()
        for recipient in recipients or []
        if (address := ((recipient or {}).get("emailAddress") or {}).get("address"))
    ]


def _time(value: Any) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def normalize(
    message: dict[str, Any], mailbox_email: str, sent_folder_id: Optional[str] = None
) -> NormalizedEmailMessage:
    sender = (message.get("from") or {}).get("emailAddress") or {}
    from_address = formataddr((sender.get("name") or None, sender.get("address") or ""))
    body = message.get("body") or {}
    content = body.get("content") or ""
    if (body.get("contentType") or "").lower() == "text":
        content = text_as_html(content)
    in_sent_items = bool(sent_folder_id) and message.get("parentFolderId") == sent_folder_id
    headers: dict[str, str] = {}
    for header in message.get("internetMessageHeaders") or []:
        headers.setdefault(str(header.get("name", "")).lower(), str(header.get("value", "")))

    return NormalizedEmailMessage(
        provider=MailboxProvider.MICROSOFT,
        provider_message_id=message["id"],
        internet_message_id=message.get("internetMessageId") or None,
        thread_id=message.get("conversationId") or "",
        direction=Direction.OUTBOUND if in_sent_items else direction_of(from_address, mailbox_email),
        from_address=from_address,
        to_addresses=_addresses(message.get("toRecipients")),
        cc_addresses=_addresses(message.get("ccRecipients")),
        subject=message.get("subject") or "",
        snippet=message.get("bodyPreview") or "",
        body_html=stored_body(content),
        sent_at=_time(message.get("sentDateTime") or message.get("receivedDateTime")),
        headers=headers,
    )
