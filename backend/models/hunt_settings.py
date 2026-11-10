from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class HuntSettings(Base):
    __tablename__ = "hunt_settings"
    __table_args__ = (
        CheckConstraint("page >= 1", name="ck_hunt_settings_page"),
        CheckConstraint(
            "run_credit_budget >= 0", name="ck_hunt_settings_run_credit_budget"
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true", default=True)
    page: Mapped[int] = mapped_column(Integer, server_default="1", default=1)
    run_credit_budget: Mapped[int] = mapped_column(
        Integer, server_default="25", default=25
    )
    filters_key: Mapped[Optional[str]] = mapped_column(Text, default=None)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    companies_added: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    contacts_found: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), init=False
    )
