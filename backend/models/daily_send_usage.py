from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class DailySendUsage(Base):
    __tablename__ = "daily_send_usage"
    __table_args__ = (PrimaryKeyConstraint("user_id", "usage_date"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    usage_date: Mapped[date] = mapped_column(Date)
    sends: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    follow_up_sends: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
