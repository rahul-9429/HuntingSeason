from typing import Literal, Optional

from pydantic import BaseModel, field_validator

from services.schemas.common import MAX_ITEMS, MAX_TEXT_LENGTH, is_place

Seniority = Literal["entry", "senior", "manager", "head", "director", "vp", "c_suite"]

JobFunction = Literal[
    "engineering",
    "product",
    "design",
    "data",
    "sales",
    "marketing",
    "customer_success",
    "finance",
    "operations",
    "hr",
    "legal",
    "other",
]

CompanySize = Literal[
    "1,10",
    "11,50",
    "51,200",
    "201,500",
    "501,1000",
    "1001,5000",
    "5001,10000",
]


def _clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = " ".join(value.split())
    return value[:MAX_TEXT_LENGTH] or None


class CareerProfile(BaseModel):
    current_title: Optional[str]
    seniority: Optional[Seniority]
    function: Optional[JobFunction]
    top_skills: list[str]
    industries: list[str]
    location: Optional[str]
    open_to_locations: list[str]
    company_size_history: list[CompanySize]

    @field_validator("current_title", "location")
    @classmethod
    def clean_text(cls, value: Optional[str]) -> Optional[str]:
        return _clean_text(value)

    @field_validator("top_skills", "industries", "open_to_locations")
    @classmethod
    def clean_list(cls, values: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned = []
        for value in values:
            text = _clean_text(value)
            if text and text.lower() not in seen:
                seen.add(text.lower())
                cleaned.append(text)
        return cleaned[:MAX_ITEMS]

    @field_validator("open_to_locations")
    @classmethod
    def drop_remote(cls, values: list[str]) -> list[str]:
        return [v for v in values if is_place(v)]

    @field_validator("company_size_history")
    @classmethod
    def clean_sizes(cls, values: list[CompanySize]) -> list[CompanySize]:
        return list(dict.fromkeys(values))

    def is_empty(self) -> bool:
        return not any(self.model_dump().values())
