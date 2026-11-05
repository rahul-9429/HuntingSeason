from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Sequence

from models.enums import MailboxProvider
from models.mailbox import Mailbox
from services import mailbox_manager


@dataclass(frozen=True)
class SendResult:
    provider_message_id: str
    internet_message_id: str
    thread_id: str


class ProviderConfigError(Exception):
    pass


class EmailProviderError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code

    @property
    def retryable(self) -> bool:
        return self.status_code is None or self.status_code == 429 or self.status_code >= 500


class MailboxAuthError(EmailProviderError):
    pass


class NotFoundError(EmailProviderError):
    pass


class EmailProvider(ABC):
    def __init__(self, mailbox: Mailbox):
        self.mailbox_id = mailbox.id
        self.email = mailbox.email
        self.credentials = mailbox_manager.credentials_of(mailbox)

    @abstractmethod
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
    ) -> SendResult: ...

    @abstractmethod
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
        pass


def get_email_provider(mailbox: Mailbox) -> EmailProvider:
    from services.email_providers.gmail_provider import GmailProvider
    from services.email_providers.microsoft_provider import MicrosoftProvider

    if mailbox.provider == MailboxProvider.GMAIL:
        return GmailProvider(mailbox)
    return MicrosoftProvider(mailbox)
