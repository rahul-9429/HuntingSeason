from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class EmailTemplate(Base):
    __tablename__ = "email_templates"
    __table_args__ = (
        Index(
            "ux_email_templates_one_default",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True, init=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str] = mapped_column(Text)
    signature_html: Mapped[Optional[str]] = mapped_column(Text, default=None)
    sender_name: Mapped[Optional[str]] = mapped_column(Text, default=None)
    skip_ai: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    is_generated: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
