from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ApolloCache(Base, kw_only=True):  # type: ignore[call-arg]
    __tablename__ = "apollo_cache"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    payload: Mapped[Any] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, init=False
    )
