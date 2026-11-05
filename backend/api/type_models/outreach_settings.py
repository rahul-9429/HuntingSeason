from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator, model_validator

from models.enums import Writer

ISO_WEEKDAYS = frozenset({1, 2, 3, 4, 5, 6, 7})


class OutreachSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled: bool
    writer: Writer
    writer_instructions: Optional[str]
    max_follow_ups: int
    follow_up_interval_days: int
    sender_name: Optional[str]
    signature_html: Optional[str]
    auto_send_replies: bool
    reply_booking_link: Optional[str]
    reply_facts: Optional[str]
    reply_cc: list[str]
    reply_bcc: list[str]
    min_gap_seconds: int
    max_gap_seconds: int
    updated_at: datetime
    has_default_template: bool = False
    has_profile: bool = False
    blocker: Optional[str] = None


class OutreachSettingsUpdate(BaseModel):
    enabled: bool = False
    writer: Writer = Writer.EMAIL_AGENT
    writer_instructions: Optional[str] = Field(default=None, max_length=4000)
    max_follow_ups: int = Field(default=2, ge=0, le=5)
    follow_up_interval_days: int = Field(default=3, ge=0, le=30)
    sender_name: Optional[str] = Field(default=None, max_length=200)
    signature_html: Optional[str] = Field(default=None, max_length=20_000)
    auto_send_replies: bool = False
    reply_booking_link: Optional[HttpUrl] = None
    reply_facts: Optional[str] = Field(default=None, max_length=4000)
    reply_cc: list[EmailStr] = Field(default_factory=list, max_length=10)
    reply_bcc: list[EmailStr] = Field(default_factory=list, max_length=10)
    min_gap_seconds: int = Field(default=180, ge=30, le=3600)
    max_gap_seconds: int = Field(default=900, ge=30, le=7200)


class SendScheduleRow(BaseModel):
    country: str
    days: list[int]
    start_hour: int
    end_hour: int
    timezone: Optional[str]


class EmailSendScheduleOut(BaseModel):
    enabled: bool
    rows: list[SendScheduleRow]


class EmailSendScheduleUpdate(BaseModel):
    enabled: Optional[bool] = None
    country: Optional[str] = Field(default=None, max_length=200)
    days: Optional[list[int]] = None

    @field_validator("days")
    @classmethod
    def _within_the_week(cls, days: Optional[list[int]]) -> Optional[list[int]]:
        if days is not None and (not days or not set(days) <= ISO_WEEKDAYS):
            raise ValueError("days must be a non-empty subset of 1-7, where 1 is Monday")
        return days

    @model_validator(mode="after")
    def _country_and_days_travel_together(self) -> "EmailSendScheduleUpdate":
        if (self.country is None) != (self.days is None):
            raise ValueError("country and days must be sent together")
        if self.enabled is None and self.country is None:
            raise ValueError("send enabled, or country and days, or both")
        return self


class RunQueued(BaseModel):
    queued: bool


class PreviewRequest(BaseModel):
    contact_id: int
    writer: Optional[Writer] = None
    template_id: Optional[int] = None


class PreviewOut(BaseModel):
    subject: str
    html: str
    writer: Writer
    template_id: Optional[int]
