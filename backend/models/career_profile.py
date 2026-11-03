from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CareerProfile(Base, kw_only=True):  # type: ignore[call-arg]
    __tablename__ = "career_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    # A validated api.type_models.career_profile.CareerProfile dump. Written by
    # résumé parsing, then by the user's edits.
    data: Mapped[Any] = mapped_column(JSONB)

    source_resume_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True, default=None
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
