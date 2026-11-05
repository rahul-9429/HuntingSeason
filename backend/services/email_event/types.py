import html
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import getaddresses, parseaddr
from typing import Optional, Sequence

from models.enums import Direction, MailboxProvider
from services.email_providers.utils import html_to_text, sanitize_email_html

MAX_BODY_CHARS = 1_000_000


@dataclass(frozen=True)
class NormalizedEmailMessage:
    provider: MailboxProvider
    provider_message_id: str
    internet_message_id: Optional[str]
    thread_id: str
    direction: Direction
    from_address: str
    to_addresses: list[str]
    cc_addresses: list[str]
    subject: str
    snippet: str
    body_html: str
    sent_at: datetime
    headers: dict[str, str] = field(default_factory=dict)


def text_as_html(text: str) -> str:
    return html.escape(text).replace("\r\n", "\n").replace("\n", "<br>")


def stored_body(raw_html: str) -> str:
    cleaned = sanitize_email_html(raw_html)
    if len(cleaned) <= MAX_BODY_CHARS:
        return cleaned
    return text_as_html(html_to_text(cleaned))[:MAX_BODY_CHARS]


def bare_addresses(header_values: Sequence[str]) -> list[str]:
    return [address.lower() for _, address in getaddresses(list(header_values)) if address]


def direction_of(from_address: str, mailbox_email: str) -> Direction:
    sender = parseaddr(from_address)[1].lower()
    return Direction.OUTBOUND if sender == mailbox_email.lower() else Direction.INBOUND
