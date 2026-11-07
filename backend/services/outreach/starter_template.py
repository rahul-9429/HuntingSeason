import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy import update as sql_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.email_template import EmailTemplate
from services.email_event import openai_client
from services.email_event import prompts as email_prompts
from services.email_event.openai_client import LLMError
from services.email_event.prompts import fill as email_fill
from services.email_providers.utils import html_to_text, sanitize_email_html
from services.outreach.user_info import UserInfo, get_user_info
from services.schemas.outreach import WrittenEmail

logger = logging.getLogger(__name__)

STARTER_NAME = "Written from your résumé"
_ALL_PLACEHOLDERS = ("{contact_name}", "{company_name}", "{role}")


class _Unusable(Exception):
    pass


def _require(text: str, placeholders: tuple[str, ...], what: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise _Unusable(f"{what} came back empty")
    missing = [name for name in placeholders if name not in cleaned]
    if missing:
        raise _Unusable(f"{what} is missing {', '.join(missing)}")
    return cleaned


async def _generated_row(db: AsyncSession, model, user_id: int):
    return await db.scalar(
        select(model)
        .where(model.user_id == user_id, model.is_generated.is_(True))
        .order_by(model.id)
        .limit(1)
    )


async def _has_default(db: AsyncSession, model, user_id: int) -> bool:
    return bool(
        await db.scalar(
            select(model.id).where(model.user_id == user_id, model.is_default.is_(True))
        )
    )


async def _clear_default(db: AsyncSession, model, user_id: int) -> None:
    await db.execute(
        sql_update(model)
        .where(model.user_id == user_id, model.is_default.is_(True))
        .values(is_default=False)
    )


async def _email_template(db: AsyncSession, user_id: int, user_info: UserInfo) -> None:
    existing = await _generated_row(db, EmailTemplate, user_id)
    if existing is None and await _has_default(db, EmailTemplate, user_id):
        return

    written = await openai_client.generate_structured(
        system=email_fill(email_prompts.STARTER_TEMPLATE_SYSTEM, user_info=user_info.as_prompt()),
        user=email_prompts.STARTER_TEMPLATE_USER,
        schema=WrittenEmail,
        user_id=user_id,
        purpose="Starter email template",
    )
    subject = _require(written.subject, (), "The starter subject")
    if not any(name in subject for name in ("{role}", "{company_name}")):
        raise _Unusable("The starter subject has no placeholder")
    body = _require(
        sanitize_email_html(written.body), _ALL_PLACEHOLDERS, "The starter body"
    )
    if not html_to_text(body).strip():
        raise _Unusable("The starter body had no text after sanitising")

    if existing is not None:
        existing.name = STARTER_NAME
        existing.subject = subject
        existing.body_html = body
        return
    await _clear_default(db, EmailTemplate, user_id)
    db.add(
        EmailTemplate(
            user_id=user_id,
            name=STARTER_NAME,
            subject=subject,
            body_html=body,
            skip_ai=False,
            is_default=True,
            is_generated=True,
        )
    )


async def regenerate(db: AsyncSession, user_id: int) -> None:
    try:
        user_info = await get_user_info(db, user_id)
    except Exception:
        logger.exception("Couldn't read the profile for starter templates", extra={"user_id": user_id})
        return
    if not user_info.has_profile:
        logger.info(
            "Skipping the starter template for user %s: no profile yet", user_id, extra={"user_id": user_id}
        )
        return

    try:
        await _email_template(db, user_id, user_info)
        await db.commit()
    except _Unusable as exc:
        await db.rollback()
        logger.warning(
            "Discarded the generated email starter template for user %s: %s",
            user_id,
            exc,
            extra={"user_id": user_id},
        )
    except (LLMError, IntegrityError) as exc:
        await db.rollback()
        logger.warning(
            "Couldn't write the email starter template for user %s: %s",
            user_id,
            exc,
            extra={"user_id": user_id},
        )
    except Exception:
        await db.rollback()
        logger.exception(
            "Couldn't write the email starter template for user %s",
            user_id,
            extra={"user_id": user_id},
        )
