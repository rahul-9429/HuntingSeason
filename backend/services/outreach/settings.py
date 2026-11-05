from typing import Optional, TypedDict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.email_template import EmailTemplate
from models.enums import Writer
from models.outreach_settings import OutreachSettings
from services.outreach.user_info import UserInfo


class EmailSendSchedule(TypedDict):
    enabled: bool
    overrides: dict[str, list[int]]


async def get_settings(db: AsyncSession, user_id: int) -> OutreachSettings:
    settings = await db.get(OutreachSettings, user_id)
    if settings is None:
        await db.execute(
            pg_insert(OutreachSettings)
            .values(user_id=user_id)
            .on_conflict_do_nothing(index_elements=["user_id"])
        )
        await db.commit()
        settings = await db.get(OutreachSettings, user_id)
        if settings is None:
            raise RuntimeError(f"Couldn't create outreach settings for user {user_id}")
    return settings


async def default_template(db: AsyncSession, user_id: int) -> Optional[EmailTemplate]:
    return (
        await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.user_id == user_id, EmailTemplate.is_default.is_(True)
            )
        )
    ).scalar_one_or_none()


async def get_template(db: AsyncSession, user_id: int, template_id: Optional[int]) -> Optional[EmailTemplate]:
    if template_id is None:
        return None
    return (
        await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.id == template_id, EmailTemplate.user_id == user_id
            )
        )
    ).scalar_one_or_none()


async def get_email_send_schedule(db: AsyncSession, user_id: int) -> EmailSendSchedule:
    row = (
        await db.execute(
            select(
                OutreachSettings.email_send_schedule_enabled,
                OutreachSettings.email_send_schedule,
            ).where(OutreachSettings.user_id == user_id)
        )
    ).first()
    if row is None:
        return {"enabled": False, "overrides": {}}
    enabled, overrides = row
    return {"enabled": bool(enabled), "overrides": overrides or {}}


async def set_email_send_schedule_enabled(db: AsyncSession, user_id: int, value: bool) -> None:
    settings = await get_settings(db, user_id)
    settings.email_send_schedule_enabled = value
    await db.commit()


async def set_email_send_schedule_days(
    db: AsyncSession, user_id: int, schedule_key: str, days: list[int]
) -> None:
    await get_settings(db, user_id)
    settings = await db.get(
        OutreachSettings, user_id, with_for_update=True, populate_existing=True
    )
    if settings is None:
        raise RuntimeError(f"Couldn't lock outreach settings for user {user_id}")
    settings.email_send_schedule = {**(settings.email_send_schedule or {}), schedule_key: days}
    await db.commit()


def writer_blocker(
    settings: OutreachSettings, template: Optional[EmailTemplate], user_info: UserInfo
) -> Optional[str]:
    if settings.writer == Writer.TEMPLATE and template is None:
        return "Add a default email template, or nothing will send."
    if settings.writer == Writer.EMAIL_AGENT and not user_info.has_profile:
        return "Upload a résumé or fill in your profile, or nothing will send."
    return None
