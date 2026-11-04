from typing import Literal

from pydantic import BaseModel, field_validator

from services.schemas.common import clean_texts

ContactType = Literal["hiring_manager", "recruiter", "referrer"]
ContactStage = Literal["new", "contacted", "hot", "dead"]
ContactSource = Literal["apollo", "hunter", "tavily"]
CONTACT_TYPES: tuple[ContactType, ...] = ("hiring_manager", "recruiter", "referrer")


class ManagerTitles(BaseModel):
    titles: list[str]

    @field_validator("titles")
    @classmethod
    def clean_text(cls, values: list[str]) -> list[str]:
        return clean_texts(values)


class WebPerson(BaseModel):
    name: str
    title: str
    url: str


class WebPeople(BaseModel):
    people: list[WebPerson]
