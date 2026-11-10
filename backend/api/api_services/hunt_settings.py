from sqlalchemy.ext.asyncio import AsyncSession

from api.type_models.hunt import HuntSettingsOut, HuntSettingsUpdate
from models.hunt_settings import HuntSettings
from services.hunt import auto_hunt, credits, hunt_filters
from services.hunt.settings import get_settings
from services.redis import push_task


async def _out(db: AsyncSession, user_id: int, settings: HuntSettings) -> HuntSettingsOut:
    blocker = settings.error
    if blocker is None and not await hunt_filters.has_targets(db, user_id):
        blocker = auto_hunt.NO_TARGETS
    balance = await credits.credits_left(db, user_id)
    limit = max(credits.SIGNUP_CREDITS, balance)
    return HuntSettingsOut(
        enabled=settings.enabled,
        last_run_at=settings.last_run_at,
        companies_added=settings.companies_added,
        contacts_found=settings.contacts_found,
        blocker=blocker,
        credits_left=balance,
        run_credit_budget=min(settings.run_credit_budget, limit),
        run_credit_limit=limit,
    )


async def read(db: AsyncSession, user_id: int) -> HuntSettingsOut:
    return await _out(db, user_id, await get_settings(db, user_id))


async def update(db: AsyncSession, user_id: int, req: HuntSettingsUpdate) -> HuntSettingsOut:
    settings = await get_settings(db, user_id)
    for field in req.model_fields_set:
        value = getattr(req, field)
        if value is not None:
            setattr(settings, field, value)
    await db.commit()
    await db.refresh(settings)
    return await _out(db, user_id, settings)


async def queue_run(db: AsyncSession, user_id: int) -> None:
    await get_settings(db, user_id)
    await push_task("auto_hunt", {"user_id": user_id})
