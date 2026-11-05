import html as html_lib
import re
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional, Sequence

import nh3

_EMAIL_TAGS = {"p", "br", "a", "strong", "b", "em", "i", "ul", "ol", "li"}
_SIGNATURE_TAGS = _EMAIL_TAGS | {"div", "span", "table", "tr", "td", "img"}
_URL_SCHEMES = {"http", "https", "mailto"}

_EMPTY_PARAGRAPH = re.compile(r"<p>(?:\s|&nbsp;|<br\s*/?>)*</p>", re.IGNORECASE)
_SCRIPT_OR_STYLE = re.compile(r"<(script|style)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
_LINK = re.compile(
    r"""<a\b[^>]*?\bhref\s*=\s*["']([^"']*)["'][^>]*>(.*?)</a\s*>""", re.IGNORECASE | re.DOTALL
)
_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_LI = re.compile(r"<li\b[^>]*>", re.IGNORECASE)
_BLOCK = re.compile(
    r"</?(?:p|div|tr|table|thead|tbody|ul|ol|h[1-6]|blockquote|pre|section|article|header|footer)\b[^>]*>",
    re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")
_QUOTE_HEADER = re.compile(
    r"^(?:On\b[^\n]{0,300}(?:\n[^\n]{0,300})?\bwrote:[ \t]*$"
    r"|-{2,}[ \t]*Original Message[ \t]*-{2,}"
    r"|From:[^\n]+\n(?:Sent|Date):)",
    re.MULTILINE | re.IGNORECASE,
)


def sanitize_email_html(html: str) -> str:
    cleaned = nh3.clean(
        html,
        tags=_EMAIL_TAGS,
        attributes={"a": {"href"}},
        url_schemes=_URL_SCHEMES,
        link_rel=None,
    )
    return _EMPTY_PARAGRAPH.sub("", cleaned).strip()


def sanitize_signature_html(html: str) -> str:
    cleaned = nh3.clean(
        html,
        tags=_SIGNATURE_TAGS,
        attributes={"*": {"style"}, "a": {"href"}, "img": {"src", "alt", "width", "height"}},
        url_schemes=_URL_SCHEMES,
        link_rel=None,
    )
    return _EMPTY_PARAGRAPH.sub("", cleaned).strip()


def _link_as_text(match: re.Match[str]) -> str:
    url = match.group(1).strip()
    text = _TAG.sub("", match.group(2)).strip()
    if not url or html_lib.unescape(text) == html_lib.unescape(url):
        return text or url
    return f"{text} ({url})"


def html_to_text(html: str) -> str:
    text = _SCRIPT_OR_STYLE.sub("", html)
    text = _LINK.sub(_link_as_text, text)
    text = _BR.sub("\n", text)
    text = _LI.sub("\n- ", text)
    text = _BLOCK.sub("\n", text)
    text = html_lib.unescape(_TAG.sub("", text))
    lines = [re.sub(r"[ \t\r\f\v\xa0]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def strip_quoted_reply(text: str) -> str:
    match = _QUOTE_HEADER.search(text)
    if match is None:
        return text
    return text[: match.start()].rstrip() or text


def build_quote_text(html: str, from_address: str, sent_at: datetime) -> str:
    when = sent_at.astimezone(timezone.utc)
    date = f"{when:%a, %b} {when.day}, {when.year} at {when:%H:%M} UTC"
    quoted = "\n".join(f"> {line}".rstrip() for line in html_to_text(html).split("\n"))
    return f"\n\nOn {date}, {from_address} wrote:\n{quoted}"


def header_text(value: Optional[str]) -> Optional[str]:
    return " ".join(value.split()) if value else value


def build_mime_message(
    *,
    from_header: str,
    to: str,
    subject: str,
    text: str,
    cc: Sequence[str] = (),
    bcc: Sequence[str] = (),
    reply_to: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Sequence[str] = (),
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = from_header
    message["To"] = to
    message["Subject"] = header_text(subject) or ""
    if cc:
        message["Cc"] = ", ".join(cc)
    if bcc:
        message["Bcc"] = ", ".join(bcc)
    if reply_to:
        message["Reply-To"] = reply_to
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = " ".join(references)
    message.set_content(text)
    return message
