from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from api.type_models.contacts import CamelModel, ContactOut
from models.enums import ReplyLabel

InboxFilter = Literal["all", "drafts", "hiring_manager", "recruiter", "referrer"]
Sender = Literal["me", "them"]


class ReplyDraftOut(CamelModel):
    id: str
    label: ReplyLabel
    reason: str
    subject: str
    body: str
    auto_send_at: Optional[datetime]


class MessageOut(CamelModel):
    id: str
    sender: Sender = Field(serialization_alias="from")
    body: str
    sent_at: datetime


class LastMessage(CamelModel):
    sender: Sender = Field(serialization_alias="from")
    body: str


class ThreadSummary(CamelModel):
    id: str
    contact: ContactOut
    channel: Literal["email"] = "email"
    subject: str
    unread: bool
    has_draft: bool
    updated_at: datetime
    last_message: LastMessage


class ThreadList(CamelModel):
    items: list[ThreadSummary]
    counts: dict[str, int]
    unread: int


class ThreadOut(CamelModel):
    id: str
    contact_id: str
    contact: ContactOut
    channel: Literal["email"] = "email"
    subject: str
    unread: bool
    archived: bool
    updated_at: datetime
    notes: str
    messages: list[MessageOut]
    draft: Optional[ReplyDraftOut]


class ThreadPatch(CamelModel):
    archived: Optional[bool] = None
    unread: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=5000)


class ReplyIn(CamelModel):
    body: str = Field(min_length=1, max_length=20000)
