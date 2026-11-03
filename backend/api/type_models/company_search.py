from typing import Optional

from pydantic import BaseModel, Field

from services.schemas.common import MAX_ITEMS, MAX_TEXT_LENGTH
from services.schemas.company import (
    MAX_EMPLOYEES,
    MAX_JOB_POSTED_WITHIN_DAYS,
    MAX_MIN_ACTIVE_JOB_POSTINGS,
    MIN_FOUNDED_YEAR,
    CompanyFilters,
    CompanyRow,
    MarketSegment,
)

__all__ = [
    "MAX_EMPLOYEES",
    "MAX_ITEMS",
    "MAX_JOB_POSTED_WITHIN_DAYS",
    "MAX_MIN_ACTIVE_JOB_POSTINGS",
    "MAX_TEXT_LENGTH",
    "MIN_FOUNDED_YEAR",
    "CompanyFilters",
    "CompanyRow",
    "CompanySearchRequest",
    "CompanySearchResponse",
    "JobPosting",
    "JobPostingsResponse",
    "MarketSegment",
]


class CompanySearchRequest(BaseModel):
    query: str = Field(max_length=1000)
    page: int = Field(1, ge=1)
    filters: Optional[CompanyFilters] = None
    # Let the user's career profile fill whatever the query leaves open
    use_profile: bool = True


class CompanySearchResponse(BaseModel):
    query: str
    filters: CompanyFilters
    page: int
    rows: list[CompanyRow]
    total_entries: Optional[int]
    has_more: bool
    credits_left: int
    used_profile: bool = False


class JobPosting(BaseModel):
    title: str
    url: Optional[str]
    location: Optional[str]
    posted_at: Optional[str]
    matches_role: bool


class JobPostingsResponse(BaseModel):
    org_id: str
    postings: list[JobPosting]
    matched_count: int
    total: int
    credits_left: int
