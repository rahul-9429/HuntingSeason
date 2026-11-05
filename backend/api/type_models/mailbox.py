from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models.enums import DeliveryStatus, MailboxProvider, MailboxStatus


class AuthUrl(BaseModel):
    url: str


class ConnectRequest(BaseModel):
    provider: MailboxProvider
    url: str
    redirect_uri: str


class MailboxOut(BaseModel):
    provider: MailboxProvider
    email: str
    from_name: Optional[str]
    status: MailboxStatus
    warmup_day: int
    daily_cap: int
    sends_today: int
    bounce_rate_7d: Optional[float]


class TestSendRequest(BaseModel):
    to: EmailStr
    subject: str = Field(min_length=1, max_length=998)
    body_html: str = Field(min_length=1)
    reply_to_sent_email_id: Optional[int] = None


class SentEmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mailbox_id: Optional[int]
    provider: MailboxProvider
    provider_message_id: str
    internet_message_id: Optional[str]
    thread_id: str
    subject: str
    body_html: str
    follow_up_attempt: int
    delivery_status: DeliveryStatus
    sent_at: datetime
