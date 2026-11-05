from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, PrimaryKeyConstraint, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class InboxThread(Base):
    __tablename__ = "inbox_threads"
    __table_args__ = (PrimaryKeyConstraint("mailbox_id", "thread_id"),)

    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id", ondelete="CASCADE"))
    thread_id: Mapped[str] = mapped_column(Text)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    notes: Mapped[str] = mapped_column(Text, server_default="", default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
