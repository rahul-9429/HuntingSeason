from datetime import datetime
from typing import Optional

from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from models.enums import Writer, db_enum


class OutreachSettings(Base):
    __tablename__ = "outreach_settings"
    __table_args__ = (
        CheckConstraint("max_follow_ups BETWEEN 0 AND 5", name="ck_outreach_settings_max_follow_ups"),
        CheckConstraint(
            "follow_up_interval_days >= 0", name="ck_outreach_settings_follow_up_interval_days"
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    writer: Mapped[Writer] = mapped_column(
        db_enum(Writer), server_default=Writer.EMAIL_AGENT.value, default=Writer.EMAIL_AGENT
    )
    writer_instructions: Mapped[Optional[str]] = mapped_column(Text, default=None)
    max_follow_ups: Mapped[int] = mapped_column(Integer, server_default="2", default=2)
    follow_up_interval_days: Mapped[int] = mapped_column(Integer, server_default="3", default=3)
    sender_name: Mapped[Optional[str]] = mapped_column(Text, default=None)
    signature_html: Mapped[Optional[str]] = mapped_column(Text, default=None)
    auto_send_replies: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    reply_booking_link: Mapped[Optional[str]] = mapped_column(Text, default=None)
    reply_facts: Mapped[Optional[str]] = mapped_column(Text, default=None)
    reply_cc: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'"), default_factory=list
    )
    reply_bcc: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'"), default_factory=list
    )
    min_gap_seconds: Mapped[int] = mapped_column(Integer, server_default="180", default=180)
    max_gap_seconds: Mapped[int] = mapped_column(Integer, server_default="900", default=900)
    email_send_schedule_enabled: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, server_default="true", default=True
    )
    email_send_schedule: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, server_default=text("'{}'::jsonb"), default_factory=dict
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), init=False
    )
