from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Contact(Base, kw_only=True):  # type: ignore[call-arg]
    __tablename__ = "contacts"
    __table_args__ = (
        Index(
            "ux_contacts_hunter_email",
            "email",
            unique=True,
            postgresql_where=text("source = 'hunter'"),
        ),
        Index(
            "ux_contacts_tavily_linkedin",
            "linkedin_url",
            unique=True,
            postgresql_where=text("source = 'tavily'"),
        ),
        Index("ix_contacts_lower_email", text("lower(email)")),
    )
    id: Mapped[int] = mapped_column(primary_key=True, init=False)

    source: Mapped[str] = mapped_column(Text, server_default="apollo", default="apollo")
    apollo_person_id: Mapped[Optional[str]] = mapped_column(Text, unique=True, default=None)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    first_name: Mapped[str] = mapped_column(Text)
    last_name: Mapped[Optional[str]] = mapped_column(Text, default=None)
    last_name_obfuscated: Mapped[Optional[str]] = mapped_column(Text, default=None)
    title: Mapped[Optional[str]] = mapped_column(Text, default=None)
    seniority: Mapped[Optional[str]] = mapped_column(Text, default=None)
    has_email: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    email: Mapped[Optional[str]] = mapped_column(Text, default=None)
    email_status: Mapped[Optional[str]] = mapped_column(Text, default=None)
    email_source: Mapped[Optional[str]] = mapped_column(Text, default=None)
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text, default=None)
    photo_url: Mapped[Optional[str]] = mapped_column(Text, default=None)
    city: Mapped[Optional[str]] = mapped_column(Text, default=None)
    state: Mapped[Optional[str]] = mapped_column(Text, default=None)
    country: Mapped[Optional[str]] = mapped_column(Text, default=None)
    revealed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
