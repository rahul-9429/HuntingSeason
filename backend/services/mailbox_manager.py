import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import AsyncSessionLocal
from models.enums import MailboxProvider, MailboxStatus
from models.mailbox import Mailbox
from services import crypto

logger = logging.getLogger(__name__)

_TOKEN_FIELDS = ("token", "access_token", "refresh_token")


class MailboxTakenError(Exception):
    pass


def _encrypt(credentials: dict[str, Any]) -> dict[str, Any]:
    return {
        name: crypto.encrypt(value) if name in _TOKEN_FIELDS and value else value
        for name, value in credentials.items()
    }


def credentials_of(mailbox: Mailbox) -> dict[str, Any]:
    return {
        name: crypto.decrypt(value) if name in _TOKEN_FIELDS and value else value
        for name, value in mailbox.credentials.items()
    }


async def get_for_user(db: AsyncSession, user_id: int) -> Optional[Mailbox]:
    return (
        await db.execute(select(Mailbox).where(Mailbox.user_id == user_id))
    ).scalar_one_or_none()


async def get(mailbox_id: int) -> Optional[Mailbox]:
    async with AsyncSessionLocal() as db:
        return await db.get(Mailbox, mailbox_id)


async def find_by_email(db: AsyncSession, email: str) -> Optional[Mailbox]:
    return (
        await db.execute(select(Mailbox).where(func.lower(Mailbox.email) == email.strip().lower()))
    ).scalar_one_or_none()


async def find_by_outlook_subscription(db: AsyncSession, subscription_id: str) -> Optional[Mailbox]:
    subscriptions = Mailbox.outlook_subscriptions
    return (
        await db.execute(
            select(Mailbox).where(
                or_(
                    subscriptions["inbox"]["id"].astext == subscription_id,
                    subscriptions["sent"]["id"].astext == subscription_id,
                )
            )
        )
    ).scalar_one_or_none()


async def active(provider: Optional[MailboxProvider] = None) -> list[Mailbox]:
    async with AsyncSessionLocal() as db:
        query = select(Mailbox).where(Mailbox.status == MailboxStatus.ACTIVE)
        if provider is not None:
            query = query.where(Mailbox.provider == provider)
        return list((await db.execute(query.order_by(Mailbox.id))).scalars())


async def is_taken(db: AsyncSession, email: str, user_id: int) -> bool:
    taken = await db.scalar(
        select(Mailbox.id).where(
            func.lower(Mailbox.email) == email.lower(), Mailbox.user_id != user_id
        )
    )
    return taken is not None


async def connect(
    db: AsyncSession,
    *,
    user_id: int,
    provider: MailboxProvider,
    email: str,
    from_name: Optional[str],
    credentials: dict[str, Any],
) -> Mailbox:
    if await is_taken(db, email, user_id):
        raise MailboxTakenError(email)

    mailbox = (
        await db.execute(
            select(Mailbox)
            .where(Mailbox.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if mailbox is None:
        mailbox = Mailbox(
            user_id=user_id,
            provider=provider,
            email=email,
            from_name=from_name,
            credentials=_encrypt(credentials),
        )
        db.add(mailbox)
    else:
        if mailbox.provider != provider or mailbox.email.lower() != email.lower():
            mailbox.gmail_history_id = None
            mailbox.gmail_watch_expires_at = None
            mailbox.outlook_subscriptions = None
        mailbox.provider = provider
        mailbox.email = email
        mailbox.from_name = from_name
        mailbox.credentials = _encrypt(credentials)
        mailbox.status = MailboxStatus.ACTIVE

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise MailboxTakenError(email) from exc
    logger.info(
        "User %s connected %s mailbox %s",
        user_id,
        provider.value,
        mailbox.id,
        extra={"user_id": user_id, "mailbox_id": mailbox.id, "provider": provider.value},
    )
    return mailbox


async def delete_for_user(db: AsyncSession, user_id: int) -> None:
    await db.execute(delete(Mailbox).where(Mailbox.user_id == user_id))
    await db.commit()


async def save_credentials(mailbox_id: int, credentials: dict[str, Any]) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Mailbox).where(Mailbox.id == mailbox_id).values(credentials=_encrypt(credentials))
        )
        await db.commit()


async def save_gmail_watch(mailbox_id: int, history_id: int, expires_at: datetime) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Mailbox)
            .where(Mailbox.id == mailbox_id)
            .values(
                gmail_history_id=func.coalesce(Mailbox.gmail_history_id, history_id),
                gmail_watch_expires_at=expires_at,
            )
        )
        await db.commit()


async def save_gmail_cursor(mailbox_id: int, history_id: int, *, force: bool = False) -> None:
    async with AsyncSessionLocal() as db:
        query = update(Mailbox).where(Mailbox.id == mailbox_id)
        if not force:
            query = query.where(
                or_(Mailbox.gmail_history_id.is_(None), Mailbox.gmail_history_id < history_id)
            )
        await db.execute(query.values(gmail_history_id=history_id))
        await db.commit()


async def save_outlook_subscriptions(
    mailbox_id: int, subscriptions: Optional[dict[str, Any]]
) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Mailbox)
            .where(Mailbox.id == mailbox_id)
            .values(outlook_subscriptions=subscriptions)
        )
        await db.commit()


async def set_status(mailbox_id: int, status: MailboxStatus) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(update(Mailbox).where(Mailbox.id == mailbox_id).values(status=status))
        await db.commit()
    logger.warning(
        "Mailbox %s is now %s",
        mailbox_id,
        status.value,
        extra={"mailbox_id": mailbox_id, "mailbox_status": status.value},
    )
