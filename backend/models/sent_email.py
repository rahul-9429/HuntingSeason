from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from models.enums import DeliveryStatus, MailboxProvider, Writer, db_enum


class SentEmail(Base):
    __tablename__ = "sent_emails"
    __table_args__ = (
        UniqueConstraint("provider", "provider_message_id"),
        Index("ix_sent_emails_mailbox_id_thread_id", "mailbox_id", "thread_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, init=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mailbox_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("mailboxes.id", ondelete="SET NULL")
    )
    provider: Mapped[MailboxProvider] = mapped_column(db_enum(MailboxProvider))
    provider_message_id: Mapped[str] = mapped_column(Text)
    thread_id: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str] = mapped_column(Text)
    internet_message_id: Mapped[Optional[str]] = mapped_column(Text, default=None)
    user_contact_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user_contacts.id", ondelete="SET NULL"), index=True, default=None
    )
    user_company_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user_companies.id", ondelete="SET NULL"), default=None
    )
    template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("email_templates.id", ondelete="SET NULL"), default=None
    )
    writer: Mapped[Optional[Writer]] = mapped_column(db_enum(Writer), default=None)
    follow_up_attempt: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        db_enum(DeliveryStatus),
        server_default=DeliveryStatus.SENT.value,
        default=DeliveryStatus.SENT,
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
