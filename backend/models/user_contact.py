from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class UserContact(Base, kw_only=True):  # type: ignore[call-arg]
    __tablename__ = "user_contacts"
    __table_args__ = (
        UniqueConstraint("user_id", "contact_id"),
        Index("ix_user_contacts_user_id_stage", "user_id", "stage"),
        Index(
            "ix_user_contacts_user_id_relevance",
            "user_id",
            text("relevance DESC"),
            text("found_at DESC"),
            "id",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True, init=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    user_company_id: Mapped[int] = mapped_column(
        ForeignKey("user_companies.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(Text)
    relevance: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(Text, server_default="new", default="new")
    found_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )

    stage_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    ai_stops_outreach: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False
    )
    follow_up_count: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    first_contacted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    replied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
