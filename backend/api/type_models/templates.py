from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    subject: str
    body_html: str
    signature_html: Optional[str]
    sender_name: Optional[str]
    skip_ai: bool
    is_default: bool
    is_generated: bool
    created_at: datetime


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=1, max_length=998)
    body_html: str = Field(min_length=1, max_length=50_000)
    signature_html: Optional[str] = Field(default=None, max_length=20_000)
    sender_name: Optional[str] = Field(default=None, max_length=200)
    skip_ai: bool = False
    is_default: bool = False


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    subject: Optional[str] = Field(default=None, min_length=1, max_length=998)
    body_html: Optional[str] = Field(default=None, min_length=1, max_length=50_000)
    signature_html: Optional[str] = Field(default=None, max_length=20_000)
    sender_name: Optional[str] = Field(default=None, max_length=200)
    skip_ai: Optional[bool] = None
    is_default: Optional[bool] = None
