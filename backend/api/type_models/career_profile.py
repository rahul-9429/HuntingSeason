from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

from services.schemas.career_profile import CareerProfile

ResumeStatus = Literal["parsing", "parsed", "failed"]

MAX_RESUME_BYTES = 5 * 1024 * 1024


class ResumeOut(BaseModel):
    id: int
    file_name: str
    status: ResumeStatus
    error: Optional[str]
    created_at: datetime
    parsed_at: Optional[datetime]
    profile: Optional[CareerProfile]
