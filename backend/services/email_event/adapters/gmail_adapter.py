import base64
import html
import re
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from models.enums import Direction, MailboxProvider
from services.email_event.types import (
    NormalizedEmailMessage,
    bare_addresses,
    direction_of,
    stored_body,
    text_as_html,
)

_CHARSET = re.compile(r"""charset\s*=\s*["']?([\w.:-]+)""", re.IGNORECASE)


def _parts(part: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield part
    if part.get("mimeType") == "message/rfc822":
        return
    for child in part.get("parts") or []:
        yield from _parts(child)


def _decoded(part: dict[str, Any]) -> str:
    data = (part.get("body") or {}).get("data") or ""
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    content_type = next(
        (h.get("value", "") for h in part.get("headers") or [] if h.get("name", "").lower() == "content-type"),
        "",
    )
    charset = _CHARSET.search(content_type)
    try:
        return raw.decode(charset.group(1) if charset else "utf-8", errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _first_part(payload: dict[str, Any], mime_type: str) -> Optional[str]:
    for part in _parts(payload):
        if (
            part.get("mimeType") == mime_type
            and not part.get("filename")
            and (part.get("body") or {}).get("data")
        ):
            return _decoded(part)
    return None


def _body(payload: dict[str, Any]) -> str:
    rich = _first_part(payload, "text/html")
    if rich is not None:
        return rich
    plain = _first_part(payload, "text/plain")
    return text_as_html(plain) if plain else ""


def is_draft(message: dict[str, Any]) -> bool:
    return "DRAFT" in (message.get("labelIds") or [])


def normalize(message: dict[str, Any], mailbox_email: str) -> NormalizedEmailMessage:
    payload = message.get("payload") or {}
    headers: dict[str, str] = {}
    for header in payload.get("headers") or []:
        headers.setdefault(header.get("name", "").lower(), header.get("value", ""))

    from_address = headers.get("from", "")
    sent = "SENT" in (message.get("labelIds") or [])
    return NormalizedEmailMessage(
        provider=MailboxProvider.GMAIL,
        provider_message_id=message["id"],
        internet_message_id=headers.get("message-id") or None,
        thread_id=message["threadId"],
        direction=Direction.OUTBOUND if sent else direction_of(from_address, mailbox_email),
        from_address=from_address,
        to_addresses=bare_addresses([headers["to"]] if "to" in headers else []),
        cc_addresses=bare_addresses([headers["cc"]] if "cc" in headers else []),
        subject=headers.get("subject", ""),
        snippet=html.unescape(message.get("snippet") or ""),
        body_html=stored_body(_body(payload)),
        sent_at=datetime.fromtimestamp(int(message.get("internalDate") or 0) / 1000, timezone.utc),
        headers=headers,
    )
