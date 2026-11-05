from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

Hue = Literal["slate", "blue", "indigo", "teal", "gray", "sky"]
RemotePreference = Literal["none", "country", "apac", "global"]
Timezone = Literal["IST (UTC+5:30)", "SGT (UTC+8:00)", "GST (UTC+4:00)", "GMT (UTC+0:00)", ""]
TargetSeniority = Literal["Mid", "Senior", "Staff", "Principal"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class GeneralInfo(CamelModel):
    name: str = Field(default="", max_length=200)
    headline: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=320)
    phone: str = Field(default="", max_length=50)
    location: str = Field(default="", max_length=200)
    timezone: str = Field(default="", max_length=50)
    linkedin: str = Field(default="", max_length=500)
    portfolio: str = Field(default="", max_length=500)
    bio: str = Field(default="", max_length=280)
    years_experience: int = Field(default=0, ge=0, le=70)
    current_company: str = Field(default="", max_length=200)
    pitch: str = Field(default="", max_length=500)


class ExperienceItem(CamelModel):
    id: str
    role: str
    company: str
    hue: Hue
    start: str
    end: str
    location: str
    highlights: list[str]
    skills: list[str]


class Education(CamelModel):
    degree: str
    school: str
    years: str


class ExperienceTimeline(CamelModel):
    items: list[ExperienceItem]
    education: Optional[Education]


class TargetLocation(CamelModel):
    country: str = Field(min_length=1, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)


class Salary(CamelModel):
    current: float = Field(default=0, ge=0)
    expected_min: float = Field(default=0, ge=0)
    expected_target: float = Field(default=0, ge=0)


class Culture(CamelModel):
    work_modes: list[str] = Field(default_factory=list, max_length=10)
    company_stage: list[str] = Field(default_factory=list, max_length=10)
    team_size: str = Field(default="", max_length=20)
    pace: str = Field(default="", max_length=20)


class Preferences(CamelModel):
    roles: list[str] = Field(default_factory=list, max_length=20)
    seniority: list[str] = Field(default_factory=list, max_length=10)
    locations: list[TargetLocation] = Field(default_factory=list, max_length=20)
    remote: RemotePreference = "none"
    salary: Salary = Field(default_factory=Salary)
    culture: Culture = Field(default_factory=Culture)


class ResumeRole(BaseModel):
    role: str
    company: str
    start: str
    end: str
    location: str
    highlights: list[str]
    skills: list[str]


class ResumeEducation(BaseModel):
    degree: str
    school: str
    years: str


class ResumeLocation(BaseModel):
    country: str
    city: Optional[str]


class ResumeDetails(BaseModel):
    name: str
    headline: str
    email: str
    phone: str
    location: str
    timezone: Timezone
    linkedin: str
    portfolio: str
    bio: str
    pitch: str
    years_experience: int
    current_company: str
    roles: list[ResumeRole]
    education: Optional[ResumeEducation]
    target_roles: list[str]
    target_seniority: list[TargetSeniority]
    target_locations: list[ResumeLocation]
    open_to_remote: bool
