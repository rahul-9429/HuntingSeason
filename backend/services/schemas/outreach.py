from pydantic import BaseModel

from models.enums import ReplyLabel


class WrittenEmail(BaseModel):
    subject: str
    body: str


class Classification(BaseModel):
    type: ReplyLabel
    reason: str


class ReplyDraft(BaseModel):
    subject: str
    body: str
