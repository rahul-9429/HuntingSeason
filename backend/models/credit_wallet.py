from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CreditWallet(Base):
    __tablename__ = "credit_wallets"
    __table_args__ = (CheckConstraint("balance >= 0", name="ck_credit_wallets_balance"),)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    balance: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    granted: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), init=False
    )
