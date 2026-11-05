import asyncio
import base64
import binascii
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from functools import cache
from typing import Any, Optional, Sequence
from urllib.parse import quote

import httpx
import msal

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
from services.email_providers.utils import html_to_text

logger = logging.getLogger(__name__)

AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = [
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/User.Read",
]

MESSAGE_FIELDS = (
    "id,conversationId,internetMessageId,subject,from,toRecipients,ccRecipients,"
    "receivedDateTime,sentDateTime,body,bodyPreview,parentFolderId,internetMessageHeaders"
)

_IMMUTABLE_IDS = {"Prefer": 'IdType="ImmutableId"'}
_REFRESH_MARGIN = timedelta(seconds=60)
_MAX_THROTTLE_RETRIES = 3
_RECONNECT_ERRORS = {"invalid_grant", "interaction_required"}

_client = httpx.AsyncClient(base_url="https://graph.microsoft.com/v1.0", timeout=30)
_msal_http_cache: dict[Any, Any] = {}


async def close_client() -> None:
    await _client.aclose()


@cache
def _client_secrets() -> tuple[str, str]:
    raw = os.getenv("MSFT_CLIENT_SECRETS_B64")
    if not raw:
        raise ProviderConfigError("MSFT_CLIENT_SECRETS_B64 is not set")
    try:
        secrets = json.loads(base64.b64decode(raw))
        return secrets["client_id"], secrets["client_secret"]
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise ProviderConfigError(
            "MSFT_CLIENT_SECRETS_B64 must be base64 of {client_id, client_secret}"
        ) from exc


def msal_app() -> Any:
    client_id, client_secret = _client_secrets()
    return msal.ConfidentialClientApplication(
        client_id,
        client_credential=client_secret,
        authority=AUTHORITY,
        http_cache=_msal_http_cache,
    )


def credentials_from_token_result(
    result: dict[str, Any], previous_refresh_token: Optional[str] = None
) -> dict[str, Any]:
    expiry = datetime.now(timezone.utc) + timedelta(seconds=int(result.get("expires_in", 3600)))
    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token") or previous_refresh_token,
        "expiry": expiry.isoformat(),
    }


def _graph_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _retry_after(response: httpx.Response) -> float:
    try:
        return min(max(float(response.headers.get("Retry-After", "")), 1.0), 60.0)
    except ValueError:
        return 5.0


def _error(response: httpx.Response, action: str) -> EmailProviderError:
    if response.status_code == 404:
        return NotFoundError(f"Graph {action} returned 404", status_code=404)
    logger.warning(
        "Graph %s returned %s: %s",
        action,
        response.status_code,
        response.text[:500],
        extra={"graph_action": action, "status_code": response.status_code},
    )
    return EmailProviderError(
        f"Graph {action} failed ({response.status_code})", status_code=response.status_code
    )


def _json_or_raise(response: httpx.Response, expected: int, action: str) -> dict[str, Any]:
    if response.status_code != expected:
        raise _error(response, action)
    try:
        body = response.json()
    except ValueError as exc:
        raise EmailProviderError(f"Graph {action} returned an unreadable response") from exc
    return body if isinstance(body, dict) else {}


def _recipients(addresses: Sequence[str]) -> list[dict[str, Any]]:
    return [{"emailAddress": {"address": address}} for address in addresses]


def _message_path(message_id: str, action: str = "") -> str:
    path = f"/me/messages/{quote(message_id, safe='')}"
    return f"{path}/{action}" if action else path


async def get_me(access_token: str) -> dict[str, Any]:
    try:
        response = await _client.get("/me", headers={"Authorization": f"Bearer {access_token}"})
    except httpx.HTTPError as exc:
        raise EmailProviderError("Couldn't reach Microsoft Graph") from exc
    return _json_or_raise(response, 200, "read profile")


class MicrosoftProvider(EmailProvider):
    def __init__(self, mailbox: Mailbox):
        super().__init__(mailbox)
        self._token_lock = asyncio.Lock()
        self._sent_folder_id: Optional[str] = None

    async def sent_folder_id(self) -> Optional[str]:
        if self._sent_folder_id is None:
            try:
                folder = _json_or_raise(
                    await self._graph("GET", "/me/mailFolders/SentItems", params={"$select": "id"}),
                    200,
                    "read the Sent Items folder",
                )
                self._sent_folder_id = folder.get("id")
            except EmailProviderError:
                return None
        return self._sent_folder_id

    async def _access_token(self, *, force_refresh: bool = False) -> str:
        async with self._token_lock:
            token = self.credentials.get("access_token")
            expiry = self.credentials.get("expiry")
            fresh = (
                token
                and expiry
                and datetime.fromisoformat(expiry) > datetime.now(timezone.utc) + _REFRESH_MARGIN
            )
            if fresh and not force_refresh:
                return str(token)

            refresh_token = self.credentials.get("refresh_token")
            if not refresh_token:
                await mailbox_manager.set_status(self.mailbox_id, MailboxStatus.NEEDS_RECONNECT)
                raise MailboxAuthError("The mailbox has no refresh token; reconnect it")
            try:
                result = await asyncio.to_thread(
                    lambda: msal_app().acquire_token_by_refresh_token(refresh_token, scopes=SCOPES)
                )
            except OSError as exc:
                raise EmailProviderError("Couldn't reach Microsoft to refresh the token") from exc

            if "access_token" not in result:
                error = result.get("error")
                if error in _RECONNECT_ERRORS:
                    await mailbox_manager.set_status(self.mailbox_id, MailboxStatus.NEEDS_RECONNECT)
                    raise MailboxAuthError("Microsoft rejected the mailbox's grant; reconnect it")
                raise EmailProviderError(f"Microsoft token refresh failed ({error})")

            self.credentials = credentials_from_token_result(result, refresh_token)
            await mailbox_manager.save_credentials(self.mailbox_id, self.credentials)
            return str(self.credentials["access_token"])

    async def _graph(
        self,
        method: str,
        path: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        token = await self._access_token()
        refreshed = False
        throttled = 0
        while True:
            try:
                response = await _client.request(
                    method,
                    path,
                    json=json,
                    params=params,
                    headers={**_IMMUTABLE_IDS, "Authorization": f"Bearer {token}"},
                )
            except httpx.HTTPError as exc:
                raise EmailProviderError(f"Couldn't reach Microsoft Graph ({method} {path})") from exc
            if response.status_code == 401 and not refreshed:
                token = await self._access_token(force_refresh=True)
                refreshed = True
                continue
            if response.status_code == 429 and throttled < _MAX_THROTTLE_RETRIES:
                throttled += 1
                await asyncio.sleep(_retry_after(response))
                continue
            return response

    async def _discard_draft(self, draft_id: str) -> None:
        try:
            await self._graph("DELETE", _message_path(draft_id))
        except EmailProviderError:
            logger.warning(
                "Couldn't delete unsent Outlook draft %s",
                draft_id,
                extra={"mailbox_id": self.mailbox_id, "provider_message_id": draft_id},
            )

    async def _send_draft(self, draft: dict[str, Any]) -> SendResult:
        response = await self._graph("POST", _message_path(draft["id"], "send"))
        if response.status_code != 202:
            if 400 <= response.status_code < 500:
                await self._discard_draft(draft["id"])
            raise _error(response, "send")
        return SendResult(
            provider_message_id=draft["id"],
            internet_message_id=draft.get("internetMessageId") or "",
            thread_id=draft.get("conversationId") or "",
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
        draft = _json_or_raise(
            await self._graph(
                "POST",
                "/me/messages",
                json={
                    "subject": subject,
                    "body": {"contentType": "Text", "content": html_to_text(html)},
                    "toRecipients": _recipients([to]),
                    "ccRecipients": _recipients(cc),
                    "bccRecipients": _recipients(bcc),
                    "replyTo": _recipients([reply_to] if reply_to else []),
                },
            ),
            201,
            "create draft",
        )
        return await self._send_draft(draft)

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
        response = await self._graph(
            "POST", _message_path(reply_to_provider_message_id, "createReply"), json={}
        )
        if response.status_code == 404:
            logger.warning(
                "Outlook message %s is gone; sending as a new email",
                reply_to_provider_message_id,
                extra={"mailbox_id": self.mailbox_id, "thread_id": thread_id},
            )
            return await self.send_email(
                to=to, subject=subject, html=html, from_name=from_name, cc=cc, bcc=bcc
            )
        draft = _json_or_raise(response, 201, "create reply")

        patch: dict[str, Any] = {
            "subject": subject,
            "body": {"contentType": "Text", "content": html_to_text(html) + (quote_text or "")},
            "toRecipients": _recipients([to]),
        }
        if cc:
            patch["ccRecipients"] = _recipients(cc)
        if bcc:
            patch["bccRecipients"] = _recipients(bcc)
        try:
            draft = _json_or_raise(
                await self._graph("PATCH", _message_path(draft["id"]), json=patch),
                200,
                "update reply",
            )
        except EmailProviderError:
            await self._discard_draft(draft["id"])
            raise
        return await self._send_draft(draft)

    async def create_subscription(
        self, resource: str, notification_url: str, expires_at: datetime, client_state: str
    ) -> dict[str, Any]:
        return _json_or_raise(
            await self._graph(
                "POST",
                "/subscriptions",
                json={
                    "changeType": "created",
                    "notificationUrl": notification_url,
                    "resource": resource,
                    "expirationDateTime": _graph_time(expires_at),
                    "clientState": client_state,
                },
            ),
            201,
            "create subscription",
        )

    async def renew_subscription(self, subscription_id: str, expires_at: datetime) -> None:
        _json_or_raise(
            await self._graph(
                "PATCH",
                f"/subscriptions/{quote(subscription_id, safe='')}",
                json={"expirationDateTime": _graph_time(expires_at)},
            ),
            200,
            "renew subscription",
        )

    async def delete_subscription(self, subscription_id: str) -> None:
        response = await self._graph("DELETE", f"/subscriptions/{quote(subscription_id, safe='')}")
        if response.status_code not in (204, 404):
            raise _error(response, "delete subscription")

    async def get_message(self, message_id: str) -> dict[str, Any]:
        return _json_or_raise(
            await self._graph("GET", _message_path(message_id), params={"$select": MESSAGE_FIELDS}),
            200,
            "read message",
        )

    async def messages_since(self, folder: str, since: datetime) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        url: Optional[str] = f"/me/mailFolders('{folder}')/messages"
        params: Optional[dict[str, str]] = {
            "$filter": f"receivedDateTime ge {_graph_time(since)}",
            "$select": MESSAGE_FIELDS,
            "$top": "50",
        }
        while url:
            page = _json_or_raise(await self._graph("GET", url, params=params), 200, "list messages")
            messages.extend(page.get("value", []))
            url, params = page.get("@odata.nextLink"), None
        return messages
