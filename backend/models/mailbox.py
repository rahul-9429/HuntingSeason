from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from models.enums import MailboxProvider, MailboxStatus, db_enum


class Mailbox(Base):
    __tablename__ = "mailboxes"
    __table_args__ = (Index("ux_mailboxes_lower_email", text("lower(email)"), unique=True),)
    id: Mapped[int] = mapped_column(primary_key=True, init=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    provider: Mapped[MailboxProvider] = mapped_column(db_enum(MailboxProvider))
    email: Mapped[str] = mapped_column(Text)
    credentials: Mapped[dict[str, Any]] = mapped_column(JSONB)
    from_name: Mapped[Optional[str]] = mapped_column(Text, default=None)
    status: Mapped[MailboxStatus] = mapped_column(
        db_enum(MailboxStatus),
        server_default=MailboxStatus.ACTIVE.value,
        default=MailboxStatus.ACTIVE,
    )
    gmail_history_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None)
    gmail_watch_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    outlook_subscriptions: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB(none_as_null=True), default=None
    )
    next_send_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    warmup_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
