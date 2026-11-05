import asyncio
import base64
import binascii
import json
import logging
import os
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from functools import cache
from typing import Any, Callable, Optional, Sequence

from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from httplib2 import HttpLib2Error

from models.enums import MailboxStatus
from models.mailbox import Mailbox
from services import mailbox_manager
from services.email_providers.email_provider import (
    EmailProvider,
    EmailProviderError,
    MailboxAuthError,
    NotFoundError,
    ProviderConfigError,
    SendResult,
)
from services.email_providers.utils import build_mime_message, header_text, html_to_text

logger = logging.getLogger(__name__)

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
]


@cache
def client_config() -> dict[str, Any]:
    raw = os.getenv("GMAIL_CLIENT_SECRETS_B64")
    if not raw:
        raise ProviderConfigError("GMAIL_CLIENT_SECRETS_B64 is not set")
    try:
        config = json.loads(base64.b64decode(raw))
    except (binascii.Error, ValueError) as exc:
        raise ProviderConfigError("GMAIL_CLIENT_SECRETS_B64 isn't base64-encoded JSON") from exc
    if not isinstance(config, dict) or "web" not in config:
        raise ProviderConfigError('GMAIL_CLIENT_SECRETS_B64 must be a Google "web" OAuth client')
    return config


@cache
def pubsub_topic() -> str:
    topic = os.getenv("GMAIL_PUBSUB_TOPIC", "").strip()
    if not topic:
        raise ProviderConfigError("GMAIL_PUBSUB_TOPIC is not set")
    if not topic.startswith("projects/"):
        raise ProviderConfigError(
            "GMAIL_PUBSUB_TOPIC must look like projects/{project}/topics/{topic}"
        )
    return topic


def credentials_to_dict(credentials: Credentials) -> dict[str, Any]:
    expiry = credentials.expiry
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "expiry": expiry.replace(tzinfo=timezone.utc).isoformat() if expiry else None,
    }


def _naive_utc(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


def _raw(message: EmailMessage) -> str:
    return base64.urlsafe_b64encode(message.as_bytes()).decode()


class GmailProvider(EmailProvider):
    def __init__(self, mailbox: Mailbox):
        super().__init__(mailbox)
        web = client_config()["web"]
        self._creds = Credentials(
            token=self.credentials.get("token"),
            refresh_token=self.credentials.get("refresh_token"),
            token_uri=web.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=web["client_id"],
            client_secret=web["client_secret"],
            scopes=SCOPES,
            expiry=_naive_utc(self.credentials.get("expiry")),
        )
        self._saved_token = self._creds.token
        self._service: Any = None
        self._lock = asyncio.Lock()

    async def _call(self, make_request: Callable[[Any], Any]) -> Any:
        async with self._lock:
            try:
                if not self._creds.valid:
                    await asyncio.to_thread(self._creds.refresh, Request())
                if self._service is None:
                    self._service = await asyncio.to_thread(
                        build, "gmail", "v1", credentials=self._creds, cache_discovery=False
                    )
                return await asyncio.to_thread(lambda: make_request(self._service).execute())
            except RefreshError as exc:
                if "invalid_grant" not in str(exc):
                    raise EmailProviderError(f"Google couldn't refresh the token: {exc}") from exc
                await mailbox_manager.set_status(self.mailbox_id, MailboxStatus.NEEDS_RECONNECT)
                raise MailboxAuthError("Google rejected the mailbox's grant; reconnect it") from exc
            except HttpError as exc:
                status = int(exc.resp.status)
                if status == 404:
                    raise NotFoundError("Gmail returned 404", status_code=404) from exc
                raise EmailProviderError(f"Gmail API returned {status}", status_code=status) from exc
            except (TransportError, HttpLib2Error, OSError) as exc:
                raise EmailProviderError("Couldn't reach Gmail") from exc
            finally:
                await self._save_token_if_changed()

    async def _save_token_if_changed(self) -> None:
        if self._creds.token and self._creds.token != self._saved_token:
            self.credentials = credentials_to_dict(self._creds)
            await mailbox_manager.save_credentials(self.mailbox_id, self.credentials)
            self._saved_token = self._creds.token

    async def _send(self, body: dict[str, Any]) -> SendResult:
        sent = await self._call(
            lambda gmail: gmail.users().messages().send(userId="me", body=body)
        )
        message_id: str = sent["id"]
        internet_message_id = ""
        try:
            meta = await self._call(
                lambda gmail: gmail.users()
                .messages()
                .get(userId="me", id=message_id, format="metadata", metadataHeaders=["Message-ID"])
            )
            internet_message_id = next(
                (
                    header.get("value", "")
                    for header in meta.get("payload", {}).get("headers", [])
                    if header.get("name", "").lower() == "message-id"
                ),
                "",
            )
        except EmailProviderError:
            logger.warning(
                "Couldn't read the Message-ID of sent Gmail message %s",
                message_id,
                extra={"mailbox_id": self.mailbox_id, "provider_message_id": message_id},
            )
        return SendResult(
            provider_message_id=message_id,
            internet_message_id=internet_message_id,
            thread_id=sent["threadId"],
        )

    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        from_name: Optional[str],
        cc: Sequence[str] = (),
        bcc: Sequence[str] = (),
        reply_to: Optional[str] = None,
    ) -> SendResult:
        message = build_mime_message(
            from_header=formataddr((header_text(from_name), self.email)),
            to=to,
            subject=subject,
            text=html_to_text(html),
            cc=cc,
            bcc=bcc,
            reply_to=reply_to,
        )
        return await self._send({"raw": _raw(message)})

    async def send_reply(
        self,
        *,
        reply_to_provider_message_id: str,
        reply_to_internet_message_id: str,
        references: Sequence[str],
        thread_id: str,
        to: str,
        subject: str,
        html: str,
        from_name: Optional[str],
        cc: Sequence[str] = (),
        bcc: Sequence[str] = (),
        quote_text: Optional[str] = None,
    ) -> SendResult:
        message = build_mime_message(
            from_header=formataddr((header_text(from_name), self.email)),
            to=to,
            subject=subject,
            text=html_to_text(html) + (quote_text or ""),
            cc=cc,
            bcc=bcc,
            in_reply_to=reply_to_internet_message_id,
            references=references,
        )
        try:
            return await self._send({"raw": _raw(message), "threadId": thread_id})
        except NotFoundError:
            logger.warning(
                "Gmail thread %s is gone; sending as a new email",
                thread_id,
                extra={"mailbox_id": self.mailbox_id, "thread_id": thread_id},
            )
        return await self.send_email(
            to=to, subject=subject, html=html, from_name=from_name, cc=cc, bcc=bcc
        )

    async def watch(self, topic: str) -> tuple[int, datetime]:
        response = await self._call(
            lambda gmail: gmail.users().watch(
                userId="me",
                body={"topicName": topic, "labelIds": ["INBOX", "SENT"], "labelFilterAction": "include"},
            )
        )
        expires_at = datetime.fromtimestamp(int(response["expiration"]) / 1000, timezone.utc)
        return int(response["historyId"]), expires_at

    async def stop_watch(self) -> None:
        await self._call(lambda gmail: gmail.users().stop(userId="me"))

    async def history_message_ids(self, start_history_id: int) -> tuple[dict[str, str], int]:
        message_ids: dict[str, str] = {}
        latest = start_history_id
        page_token: Optional[str] = None
        while True:

            def history_page(gmail: Any, token: Optional[str] = page_token) -> Any:
                return gmail.users().history().list(
                    userId="me",
                    startHistoryId=start_history_id,
                    historyTypes=["messageAdded", "labelAdded"],
                    pageToken=token,
                )

            page = await self._call(history_page)
            for record in page.get("history", []):
                for added in record.get("messagesAdded", []):
                    message = added.get("message") or {}
                    if message.get("id") and "DRAFT" not in message.get("labelIds", []):
                        message_ids[message["id"]] = message.get("threadId", "")
                for labelled in record.get("labelsAdded", []):
                    message = labelled.get("message") or {}
                    if message.get("id") and "SENT" in labelled.get("labelIds", []):
                        message_ids[message["id"]] = message.get("threadId", "")
            latest = max(latest, int(page.get("historyId", latest)))
            page_token = page.get("nextPageToken")
            if not page_token:
                return message_ids, latest

    async def recent_message_ids(self, query: str) -> dict[str, str]:
        message_ids: dict[str, str] = {}
        page_token: Optional[str] = None
        while True:

            def list_page(gmail: Any, token: Optional[str] = page_token) -> Any:
                return gmail.users().messages().list(userId="me", q=query, pageToken=token)

            page = await self._call(list_page)
            for message in page.get("messages", []):
                message_ids[message["id"]] = message.get("threadId", "")
            page_token = page.get("nextPageToken")
            if not page_token:
                return message_ids

    async def get_message(self, message_id: str) -> dict[str, Any]:
        message: dict[str, Any] = await self._call(
            lambda gmail: gmail.users().messages().get(userId="me", id=message_id, format="full")
        )
        return message

    async def profile_history_id(self) -> int:
        profile = await self._call(lambda gmail: gmail.users().getProfile(userId="me"))
        return int(profile["historyId"])
