from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services.errors import ServiceError
from api.type_models.outreach_settings import (
    EmailSendScheduleOut,
    EmailSendScheduleUpdate,
    OutreachSettingsOut,
    OutreachSettingsUpdate,
    PreviewOut,
    PreviewRequest,
    SendScheduleRow,
)
from models.contact import Contact
from models.enums import ProposalStatus
from models.outreach_settings import OutreachSettings
from models.reply_proposal import ReplyProposal
from models.user_contact import UserContact
from services import mailbox_manager
from services.outreach import email_contacting
from services.outreach.country_business_hours import (
    COUNTRY_BUSINESS_HOURS,
    DEFAULT_BUSINESS_HOURS,
    OTHER_COUNTRIES_KEY,
    get_business_hours,
)
from services.outreach.drafting import DraftingError
from services.outreach.settings import (
    default_template,
    get_email_send_schedule,
    get_settings,
    set_email_send_schedule_days,
    set_email_send_schedule_enabled,
    writer_blocker,
)
from services.outreach.user_info import get_user_info
from services.redis import push_task

OTHER_COUNTRIES_LABEL = "Other countries"


async def _with_readiness(
    db: AsyncSession, user_id: int, settings: OutreachSettings
) -> OutreachSettingsOut:
    template = await default_template(db, user_id)
    user_info = await get_user_info(db, user_id)
    return OutreachSettingsOut.model_validate(settings).model_copy(
        update={
            "has_default_template": template is not None,
            "has_profile": user_info.has_profile,
            "blocker": writer_blocker(settings, template, user_info),
        }
    )


async def read(db: AsyncSession, user_id: int) -> OutreachSettingsOut:
    return await _with_readiness(db, user_id, await get_settings(db, user_id))


async def update(db: AsyncSession, user_id: int, req: OutreachSettingsUpdate) -> OutreachSettingsOut:
    settings = await get_settings(db, user_id)
    for field in req.model_fields_set:
        value = getattr(req, field)
        if field == "reply_booking_link" and value is not None:
            value = str(value)
        elif field in ("reply_cc", "reply_bcc"):
            value = list(dict.fromkeys(str(address).lower() for address in value))
        setattr(settings, field, value)
    if settings.max_gap_seconds < settings.min_gap_seconds:
        await db.rollback()
        raise ServiceError("The longest gap can't be shorter than the shortest gap", status_code=422)
    if not settings.auto_send_replies:
        await db.execute(
            sql_update(ReplyProposal)
            .where(
                ReplyProposal.user_id == user_id,
                ReplyProposal.status == ProposalStatus.PENDING,
                ReplyProposal.auto_send_at.is_not(None),
            )
            .values(auto_send_at=None)
        )
    await db.commit()
    await db.refresh(settings)
    return await _with_readiness(db, user_id, settings)


def _row(
    label: str, key: str, cfg: dict[str, Any], overrides: dict[str, list[int]]
) -> SendScheduleRow:
    return SendScheduleRow(
        country=label,
        days=list(overrides.get(key) or cfg["default_days"]),
        start_hour=cfg["start_hour"],
        end_hour=cfg["end_hour"],
        timezone=cfg["timezone"],
    )


async def read_send_schedule(db: AsyncSession, user_id: int) -> EmailSendScheduleOut:
    await get_settings(db, user_id)
    schedule = await get_email_send_schedule(db, user_id)
    countries = (
        await db.execute(
            select(Contact.country)
            .join(UserContact, UserContact.contact_id == Contact.id)
            .where(UserContact.user_id == user_id)
            .distinct()
        )
    ).scalars().all()
    keys = {get_business_hours(country)[0] for country in countries}
    rows = [
        _row(name, name, cfg, schedule["overrides"])
        for name, cfg in COUNTRY_BUSINESS_HOURS.items()
        if name in keys
    ]
    if OTHER_COUNTRIES_KEY in keys:
        rows.append(
            _row(
                OTHER_COUNTRIES_LABEL,
                OTHER_COUNTRIES_KEY,
                DEFAULT_BUSINESS_HOURS,
                schedule["overrides"],
            )
        )
    return EmailSendScheduleOut(enabled=schedule["enabled"], rows=rows)


def _schedule_key(country: str) -> str:
    if country == OTHER_COUNTRIES_LABEL:
        return OTHER_COUNTRIES_KEY
    if country not in COUNTRY_BUSINESS_HOURS:
        raise ServiceError(f"Unknown country '{country}'", status_code=422)
    return country


async def update_send_schedule(
    db: AsyncSession, user_id: int, req: EmailSendScheduleUpdate
) -> EmailSendScheduleOut:
    key: Optional[str] = None if req.country is None else _schedule_key(req.country)
    if req.enabled is not None:
        await set_email_send_schedule_enabled(db, user_id, req.enabled)
    if key is not None and req.days is not None:
        await set_email_send_schedule_days(db, user_id, key, sorted(set(req.days)))
    return await read_send_schedule(db, user_id)


async def queue_run(user_id: int) -> None:
    await push_task("outreach_run", {"user_id": user_id})


async def preview(db: AsyncSession, user_id: int, req: PreviewRequest) -> PreviewOut:
    if await mailbox_manager.get_for_user(db, user_id) is None:
        raise ServiceError("Connect a mailbox first", status_code=409)
    try:
        draft = await email_contacting.preview(
            db, user_id, req.contact_id, req.writer, req.template_id
        )
    except DraftingError as exc:
        raise ServiceError(str(exc), status_code=422) from exc
    if draft is None:
        raise ServiceError("No contact with an email address has that id", status_code=404)
    return PreviewOut(
        subject=draft.subject, html=draft.html, writer=draft.writer, template_id=draft.template_id
    )
