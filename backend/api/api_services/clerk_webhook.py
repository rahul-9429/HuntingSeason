import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services.users import create_or_link_user

logger = logging.getLogger(__name__)


def _primary_email(event_data: dict[str, Any]) -> str:
    emails: list[dict[str, Any]] = event_data.get("email_addresses") or []
    primary_id = event_data.get("primary_email_address_id")
    primary = next((e for e in emails if e.get("id") == primary_id), None)
    if primary is None and emails:
        primary = emails[0]
    return ((primary or {}).get("email_address") or "").strip().lower()


def _clerk_full_name(event_data: dict[str, Any], email: str) -> str:
    first_name = (event_data.get("first_name") or "").strip()
    last_name = (event_data.get("last_name") or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    return full_name or (email.split("@")[0] if email else "New User")


async def handle_user_created(db: AsyncSession, event_data: dict[str, Any]) -> None:
    clerk_user_id = event_data.get("id")
    email = _primary_email(event_data)
    if not clerk_user_id or not email:
        logger.warning(
            "user.created without an id or email; skipping: %s",
            clerk_user_id,
            extra={"clerk_user_id": clerk_user_id},
        )
        return

    # Same create-or-link as the auth path, which may already have made this
    # row on the user's first request; this just fills in the real name.
    user_id = await create_or_link_user(
        db, clerk_user_id, email, name=_clerk_full_name(event_data, email)
    )
    logger.info(
        "user.created: Clerk user %s is user %s",
        clerk_user_id,
        user_id,
        extra={"clerk_user_id": clerk_user_id, "user_id": user_id},
    )
