from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from services.hunt import credits


async def create_or_link_user(
    db: AsyncSession,
    clerk_user_id: str,
    email: str,
    name: Optional[str] = None,
) -> int:
    """Insert a user for this Clerk id, or link the existing row with this email to it.

    Shared by the auth dependency (first login) and the ``user.created``
    webhook, which can land in either order. Only the webhook knows the real
    name; without one, a new row is named after the email and an existing
    row's name is left alone. Returns the user id.
    """
    on_conflict: dict[str, str] = {"clerk_user_id": clerk_user_id}
    if name:
        on_conflict["name"] = name

    try:
        user_id = (
            await db.execute(
                pg_insert(User)
                .values(
                    clerk_user_id=clerk_user_id,
                    email=email,
                    name=name or email.split("@")[0] or "New User",
                )
                .on_conflict_do_update(index_elements=["email"], set_=on_conflict)
                .returning(User.id)
            )
        ).scalar_one()
        await db.commit()
    except IntegrityError:
        # The ON CONFLICT target above only covers a collision on email, but
        # clerk_user_id is unique too. A Clerk account whose email changed since
        # it last signed in here already owns this id under its old email, so
        # resolve to that row rather than failing.
        await db.rollback()
        user_id = (
            await db.execute(
                select(User.id).where(User.clerk_user_id == clerk_user_id)
            )
        ).scalar_one()

    await credits.grant_signup_credits(db, user_id)
    return user_id
