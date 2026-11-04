from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Company(Base, kw_only=True):  # type: ignore[call-arg]
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True, init=False)

    apollo_org_id: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    domain: Mapped[Optional[str]] = mapped_column(Text, default=None)
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text, default=None)
    linkedin_jobs_url: Mapped[Optional[str]] = mapped_column(Text, default=None)
    logo_url: Mapped[Optional[str]] = mapped_column(Text, default=None)
    founded_year: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    employee_count: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
