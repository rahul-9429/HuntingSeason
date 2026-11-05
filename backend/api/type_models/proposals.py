from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models.enums import Direction, ProposalStatus, ReplyLabel


class ProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_contact_id: Optional[int]
    email_event_id: int
    sent_email_id: Optional[int]
    label: ReplyLabel
    reason: str
    subject: str
    body: str
    cc: list[str]
    bcc: list[str]
    status: ProposalStatus
    auto_send_at: Optional[datetime]
    expires_at: datetime
    created_at: datetime
    resolved_at: Optional[datetime]
    send_error: Optional[str]


class ProposalUpdate(BaseModel):
    subject: Optional[str] = Field(default=None, min_length=1, max_length=998)
    body: Optional[str] = Field(default=None, min_length=1, max_length=20_000)
    cc: Optional[list[EmailStr]] = Field(default=None, max_length=10)
    bcc: Optional[list[EmailStr]] = Field(default=None, max_length=10)


class ThreadMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    direction: Direction
    from_address: str
    to_addresses: list[str]
    cc_addresses: list[str]
    subject: str
    snippet: str
    body_html: str
    sent_at: datetime
    classification_label: Optional[ReplyLabel]
    classification_reason: Optional[str]
