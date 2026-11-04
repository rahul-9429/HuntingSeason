from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from models.enums import Writer
from services.schemas.contacts import (
    CONTACT_TYPES,
    ContactSource,
    ContactStage,
    ContactType,
)

__all__ = [
    "CONTACT_TYPES",
    "ContactCompany",
    "ContactList",
    "ContactOut",
    "ContactSource",
    "ContactStage",
    "ContactType",
    "Credits",
    "OutreachRequest",
    "RevealResponse",
    "Signal",
]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Signal(CamelModel):
    kind: Literal["hiring", "background", "stack", "activity", "network"]
    label: str


class ContactCompany(CamelModel):
    id: str
    name: str
    domain: Optional[str]
    logo_url: Optional[str]
    linkedin_url: Optional[str]


class ContactOut(CamelModel):
    id: str
    name: str
    title: str
    type: ContactType
    company_id: str
    location: Optional[str]
    email: Optional[str]
    email_masked: Optional[str]
    linkedin: Optional[str]
    photo_url: Optional[str]
    relevance: int
    signals: list[Signal]
    found_at: datetime
    stage: ContactStage
    revealed: bool
    source: ContactSource
    email_source: Optional[ContactSource]
    company: ContactCompany


class ContactList(CamelModel):
    items: list[ContactOut]
    counts: dict[str, int]
    next_cursor: Optional[str] = None


class Credits(CamelModel):
    used: int
    total: int


class RevealResponse(CamelModel):
    contact: ContactOut
    credits: Credits


class OutreachRequest(CamelModel):
    subject: str = Field(min_length=1, max_length=998)
    html: str = Field(min_length=1, max_length=50_000)
    writer: Optional[Writer] = None
    template_id: Optional[int] = None
