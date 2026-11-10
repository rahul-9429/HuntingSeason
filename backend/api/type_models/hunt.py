from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HuntSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    run_credit_budget: Optional[int] = Field(default=None, ge=0, le=10_000)


class HuntSettingsOut(BaseModel):
    enabled: bool
    last_run_at: Optional[datetime]
    companies_added: int
    contacts_found: int
    blocker: Optional[str]
    credits_left: int
    run_credit_budget: int
    run_credit_limit: int

    model_config = {"from_attributes": True}


class HuntQueued(BaseModel):
    queued: bool
