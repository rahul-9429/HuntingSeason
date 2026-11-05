from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    general: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB(none_as_null=True), default=None
    )
    experience: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB(none_as_null=True), default=None
    )
    preferences: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB(none_as_null=True), default=None
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), init=False
    )
