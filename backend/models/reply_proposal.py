from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from models.enums import ProposalStatus, ReplyLabel, db_enum


class ReplyProposal(Base):
    __tablename__ = "reply_proposals"
    __table_args__ = (Index("ix_reply_proposals_user_id_status", "user_id", "status"),)
    id: Mapped[int] = mapped_column(primary_key=True, init=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    email_event_id: Mapped[int] = mapped_column(
        ForeignKey("email_events.id", ondelete="CASCADE"), unique=True
    )
    label: Mapped[ReplyLabel] = mapped_column(db_enum(ReplyLabel))
    reason: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user_contact_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user_contacts.id", ondelete="SET NULL"), default=None
    )
    sent_email_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sent_emails.id", ondelete="SET NULL"), default=None
    )
    cc: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'"), default_factory=list
    )
    bcc: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'"), default_factory=list
    )
    status: Mapped[ProposalStatus] = mapped_column(
        db_enum(ProposalStatus),
        server_default=ProposalStatus.PENDING.value,
        default=ProposalStatus.PENDING,
    )
    auto_send_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    send_error: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
