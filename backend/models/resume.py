from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Resume(Base, kw_only=True):  # type: ignore[call-arg]
    __tablename__ = "resumes"
    id: Mapped[int] = mapped_column(primary_key=True, init=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # resumes/{user_id}/{uuid}.pdf in S3_BUCKET
    s3_key: Mapped[str] = mapped_column(Text, unique=True)
    file_name: Mapped[str] = mapped_column(Text)

    # parsing | parsed | failed
    status: Mapped[str] = mapped_column(Text, default="parsing")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

    # The CareerProfile as extracted, before any edits by the user
    extracted: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
    parsed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
