from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class UserCompany(Base, kw_only=True):  # type: ignore[call-arg]
    __tablename__ = "user_companies"
    __table_args__ = (UniqueConstraint("user_id", "company_id"),)
    id: Mapped[int] = mapped_column(primary_key=True, init=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    roles: Mapped[list[str]] = mapped_column(JSONB)
    locations: Mapped[list[str]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text)
    contacts_found: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, default=None)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
    searched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
