from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class User(Base, kw_only=True):  # type: ignore[call-arg]
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, init=False)

    name: Mapped[str] = mapped_column(Text, nullable=False)

    # A row that already has this email is linked to a new Clerk id on first
    # login, which is only safe because Clerk verifies the email first.
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)

    # Null for rows created before the person ever signed in.
    clerk_user_id: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, unique=True, default=None
    )

    # server_default rather than default_factory: the create-or-link upsert is a
    # Core insert, which skips the ORM's Python-side defaults.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
