from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, PrimaryKeyConstraint, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class EmailedAddress(Base):
    __tablename__ = "emailed_addresses"
    __table_args__ = (PrimaryKeyConstraint("user_id", "email"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(Text)
    first_emailed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
