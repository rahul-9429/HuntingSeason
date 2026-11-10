import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from services.errors import ServiceError
from models.credit_grant import CreditGrant
from models.credit_wallet import CreditWallet

logger = logging.getLogger(__name__)

SIGNUP_CREDITS = int(os.getenv("SIGNUP_CREDITS", "50"))
SIGNUP_GRANT = "signup"

OUT_OF_CREDITS = "You're out of credits. Top up to keep searching."


class CreditLimitReached(ServiceError):
    status_code = 429


def monthly_grant(when: Optional[datetime] = None) -> str:
    return f"monthly:{(when or datetime.now(timezone.utc)).strftime('%Y-%m')}"


async def grant(db: AsyncSession, user_id: int, amount: int, reason: str) -> bool:
    if amount <= 0:
        return False

    recorded = await db.scalar(
        pg_insert(CreditGrant)
        .values(user_id=user_id, amount=amount, reason=reason)
        .on_conflict_do_nothing(index_elements=["user_id", "reason"])
        .returning(CreditGrant.id)
    )
    if recorded is None:
        await db.rollback()
        return False

    balance = await db.scalar(
        pg_insert(CreditWallet)
        .values(user_id=user_id, balance=amount, granted=amount)
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                "balance": CreditWallet.balance + amount,
                "granted": CreditWallet.granted + amount,
            },
        )
        .returning(CreditWallet.balance)
    )
    await db.commit()
    logger.info(
        "Granted user %s %d credits (%s), balance %s",
        user_id,
        amount,
        reason,
        balance,
        extra={"user_id": user_id, "granted": amount, "reason": reason, "balance": balance},
    )
    return True


async def grant_signup_credits(db: AsyncSession, user_id: int) -> None:
    await grant(db, user_id, SIGNUP_CREDITS, SIGNUP_GRANT)


async def _spend(db: AsyncSession, user_id: int) -> Optional[int]:
    balance = await db.scalar(
        update(CreditWallet)
        .where(CreditWallet.user_id == user_id, CreditWallet.balance > 0)
        .values(balance=CreditWallet.balance - 1)
        .returning(CreditWallet.balance)
    )
    await db.commit()
    return balance


async def reserve_credit(db: AsyncSession, user_id: int, purpose: str) -> None:
    balance = await _spend(db, user_id)
    if balance is None:
        await grant(db, user_id, SIGNUP_CREDITS, SIGNUP_GRANT)
        balance = await _spend(db, user_id)

    if balance is None:
        logger.info(
            "User %s has no credits left (%s)",
            user_id,
            purpose,
            extra={"user_id": user_id, "purpose": purpose},
        )
        raise CreditLimitReached(OUT_OF_CREDITS)
    logger.info(
        "User %s spent a credit on %s (%d left)",
        user_id,
        purpose,
        balance,
        extra={"user_id": user_id, "purpose": purpose, "balance": balance},
    )


async def refund_credit(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(CreditWallet)
        .where(CreditWallet.user_id == user_id)
        .values(balance=func.least(CreditWallet.balance + 1, CreditWallet.granted))
    )
    await db.commit()


async def wallet(db: AsyncSession, user_id: int) -> tuple[int, int]:
    row = (
        await db.execute(
            select(CreditWallet.balance, CreditWallet.granted).where(
                CreditWallet.user_id == user_id
            )
        )
    ).first()
    if row is None:
        return SIGNUP_CREDITS, SIGNUP_CREDITS
    return row.balance, row.granted


async def credits_left(db: AsyncSession, user_id: int) -> int:
    balance, _ = await wallet(db, user_id)
    return balance
