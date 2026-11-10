import re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, field_validator, model_validator

from services.schemas.common import clean_texts, is_place
from services.schemas.common import unique as _unique

MarketSegment = Literal[
    "b2b",
    "b2c",
    "b2b2c",
    "e-commerce",
    "fintech",
    "d2c",
    "non-profit",
    "saas",
    "consulting",
    "services",
    "retail",
]

MAX_EMPLOYEES = 1_000_000
MAX_JOB_POSTED_WITHIN_DAYS = 365
MAX_MIN_ACTIVE_JOB_POSTINGS = 10_000
MIN_FOUNDED_YEAR = 1800

_EMPLOYEE_RANGE = re.compile(r"(\d+)(?:[,\-–](\d*)|\+)")


class CompanyFilters(BaseModel):
    hiring_locations: list[str]
    company_locations: list[str]
    employee_ranges: list[str]
    keyword_tags: list[str]
    market_segments: list[MarketSegment]
    job_title_signals: list[str]
    min_active_job_postings: Optional[int]
    job_posted_within_days: Optional[int]
    founded_year_min: Optional[int]
    founded_year_max: Optional[int]

    @field_validator("hiring_locations", "company_locations", "keyword_tags", "job_title_signals")
    @classmethod
    def clean_text(cls, values: list[str]) -> list[str]:
        return clean_texts(values)

    @field_validator("hiring_locations", "company_locations")
    @classmethod
    def drop_remote(cls, values: list[str]) -> list[str]:
        return [v for v in values if is_place(v)]

    @field_validator("employee_ranges")
    @classmethod
    def clean_employee_ranges(cls, values: list[str]) -> list[str]:
        ranges = []
        for value in values:
            match = _EMPLOYEE_RANGE.fullmatch(value.replace(" ", ""))
            if not match:
                continue
            low = int(match[1])
            high = int(match[2]) if match[2] else MAX_EMPLOYEES
            low, high = sorted((min(low, MAX_EMPLOYEES), min(high, MAX_EMPLOYEES)))
            ranges.append(f"{max(low, 1)},{max(high, 1)}")
        return _unique(ranges)

    @field_validator("market_segments")
    @classmethod
    def clean_segments(cls, values: list[MarketSegment]) -> list[MarketSegment]:
        return list(dict.fromkeys(values))

    @field_validator("min_active_job_postings")
    @classmethod
    def clean_min_jobs(cls, value: Optional[int]) -> Optional[int]:
        return value if value is not None and 1 <= value <= MAX_MIN_ACTIVE_JOB_POSTINGS else None

    @field_validator("job_posted_within_days")
    @classmethod
    def clean_posted_within(cls, value: Optional[int]) -> Optional[int]:
        return None if value is None or value < 1 else min(value, MAX_JOB_POSTED_WITHIN_DAYS)

    @field_validator("founded_year_min", "founded_year_max")
    @classmethod
    def clean_year(cls, value: Optional[int]) -> Optional[int]:
        in_range = value is not None and MIN_FOUNDED_YEAR <= value <= date.today().year + 1
        return value if in_range else None

    @model_validator(mode="after")
    def order_years(self) -> "CompanyFilters":
        low, high = self.founded_year_min, self.founded_year_max
        if low is not None and high is not None and low > high:
            self.founded_year_min, self.founded_year_max = high, low
        return self

    def is_empty(self) -> bool:
        return not any(self.model_dump().values())


class CompanyRow(BaseModel):
    apollo_org_id: str
    company_name: str
    domain: Optional[str]
    linkedin_url: Optional[str]
    linkedin_jobs_url: Optional[str]
    logo_url: Optional[str]
    founded_year: Optional[int]
    employee_count: Optional[int] = None
