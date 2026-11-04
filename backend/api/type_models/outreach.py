from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from services.schemas.common import clean_texts

OutreachStatus = Literal["searching", "ready", "no_contacts", "failed"]


class AddToOutreachRequest(BaseModel):
    apollo_org_id: str = Field(pattern=r"^[0-9a-f]{24}$")
    roles: list[str] = []
    locations: list[str] = []

    @field_validator("roles", "locations")
    @classmethod
    def clean_text(cls, values: list[str]) -> list[str]:
        return clean_texts(values)


class OutreachCompany(BaseModel):
    apollo_org_id: str
    status: OutreachStatus
    contacts_found: int
    error: Optional[str]
    searched_at: datetime
