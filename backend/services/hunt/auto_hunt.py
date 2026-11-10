import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import ColumnElement, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import AsyncSessionLocal
from models.company import Company
from models.hunt_settings import HuntSettings
from models.user_company import UserCompany
from services.errors import ServiceError
from services.hunt import company_search, contact_finder, credits, hunt_filters, targets
from services.hunt.company_search import MAX_PAGES
from services.hunt.credits import CreditLimitReached
from services.hunt.settings import get_settings
from services.redis import key, locks
from services.schemas.company import CompanyFilters, CompanyRow

logger = logging.getLogger(__name__)

RUN_LOCK_TTL = 30 * 60
SEARCH_COST = 1
FALLBACK_SEARCHES = 2
COMPANY_COST = contact_finder.MAX_CONTACTS + FALLBACK_SEARCHES
HUNT_EVERY = timedelta(hours=float(os.getenv("AUTO_HUNT_EVERY_HOURS", "24")))

NO_TARGETS = (
    "Add your target roles and locations, or upload your résumé, "
    "so Auto-Hunt knows what to look for"
)
NO_CREDITS = (
    "This run's credit budget is spent. "
    "Auto-Hunt picks up where it left off on its next run."
)
INTERRUPTED = "The hunt was interrupted, it runs again on its next turn"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def due_at(now: Optional[datetime] = None) -> datetime:
    return (now or _now()) - HUNT_EVERY


def is_due(now: Optional[datetime] = None) -> ColumnElement[bool]:
    return or_(
        HuntSettings.last_run_at.is_(None), HuntSettings.last_run_at <= due_at(now)
    )


def locations_for(filters: CompanyFilters) -> list[str]:
    return filters.hiring_locations or filters.company_locations


async def reserve_for(db: AsyncSession, user_id: int, run_credit_budget: int) -> int:
    balance = await credits.credits_left(db, user_id)
    return max(0, balance - run_credit_budget)


async def _claim_run(db: AsyncSession, user_id: int) -> bool:
    claimed = await db.scalar(
        update(HuntSettings)
        .where(
            HuntSettings.user_id == user_id,
            HuntSettings.enabled.is_(True),
            is_due(),
        )
        .values(last_run_at=_now(), companies_added=0, contacts_found=0, error=None)
        .returning(HuntSettings.user_id)
    )
    await db.commit()
    return claimed is not None


async def _record(db: AsyncSession, user_id: int, **values: object) -> None:
    await db.execute(update(HuntSettings).where(HuntSettings.user_id == user_id).values(**values))
    await db.commit()


async def _already_targeted(db: AsyncSession, user_id: int, org_ids: list[str]) -> set[str]:
    if not org_ids:
        return set()
    rows = await db.scalars(
        select(Company.apollo_org_id)
        .join(UserCompany, UserCompany.company_id == Company.id)
        .where(UserCompany.user_id == user_id, Company.apollo_org_id.in_(org_ids))
    )
    return set(rows.all())


async def _search_company(
    db: AsyncSession, user_id: int, row: CompanyRow, filters: CompanyFilters
) -> Optional[int]:
    company_id = await targets.company_id_for(db, row.apollo_org_id)
    if company_id is None:
        return None
    user_company_id = await targets.start_search(
        db, user_id, company_id, filters.job_title_signals, locations_for(filters)
    )
    await db.commit()
    if user_company_id is None:
        return None
    await contact_finder.find_contacts(user_company_id)
    found = await db.scalar(
        select(UserCompany.contacts_found).where(UserCompany.id == user_company_id)
    )
    return found or 0


class _Sweep:
    def __init__(
        self,
        db: AsyncSession,
        user_id: int,
        filters: CompanyFilters,
        page: int,
        reserve: int = 0,
    ):
        self.db = db
        self.user_id = user_id
        self.filters = filters
        self.page = page
        self.reserve = reserve
        self.companies = 0
        self.contacts = 0
        self.error: Optional[str] = None

    async def _room_for(self, cost: int) -> bool:
        left = await credits.credits_left(self.db, self.user_id)
        return left - cost >= self.reserve

    async def run(self) -> None:
        while True:
            if not await self._room_for(SEARCH_COST):
                self.error = NO_CREDITS
                return
            rows, has_more = await company_search.fetch_page(
                self.db, self.filters, self.page, self.user_id
            )
            if not await self._page(rows):
                return
            if not has_more or self.page >= MAX_PAGES:
                self.page = 1
                return
            self.page += 1

    async def _page(self, rows: list[CompanyRow]) -> bool:
        taken = await _already_targeted(self.db, self.user_id, [r.apollo_org_id for r in rows])
        for row in rows:
            if row.apollo_org_id in taken:
                continue
            if not await self._room_for(COMPANY_COST):
                self.error = NO_CREDITS
                return False
            found = await _search_company(self.db, self.user_id, row, self.filters)
            if found is not None:
                self.companies += 1
                self.contacts += found
        return True


async def run(user_id: int, *, scheduled: bool = False) -> None:
    lock_key = key("hunt", "lock", "user", user_id)
    async with locks.lock(lock_key, RUN_LOCK_TTL) as acquired:
        if not acquired:
            logger.info(
                "Auto-Hunt for user %s is already running", user_id, extra={"user_id": user_id}
            )
            return
        await _run(user_id, scheduled)


async def _run(user_id: int, scheduled: bool) -> None:
    async with AsyncSessionLocal() as db:
        settings = await get_settings(db, user_id)
        if not settings.enabled:
            logger.info("Auto-Hunt is off for user %s", user_id, extra={"user_id": user_id})
            return
        if scheduled:
            if not await _claim_run(db, user_id):
                return
        else:
            await _record(
                db, user_id, last_run_at=_now(), companies_added=0, contacts_found=0, error=None
            )
        page, stored_key = settings.page, settings.filters_key

        try:
            found = await hunt_filters.hunt_filters(db, user_id)
        except ServiceError as exc:
            await _record(db, user_id, error=exc.detail)
            logger.warning(
                "Auto-Hunt for user %s couldn't build filters: %s",
                user_id,
                exc.detail,
                extra={"user_id": user_id},
            )
            return
        if found is None:
            await _record(db, user_id, error=NO_TARGETS)
            logger.info(
                "Auto-Hunt for user %s has nothing to search on",
                user_id,
                extra={"user_id": user_id},
            )
            return

        filters, new_key = found
        if new_key != stored_key:
            page = 1
            await _record(db, user_id, page=1, filters_key=new_key)

        reserve = await reserve_for(db, user_id, settings.run_credit_budget)
        sweep = _Sweep(db, user_id, filters, page, reserve)
        try:
            await sweep.run()
        except CreditLimitReached:
            sweep.error = NO_CREDITS
        except ServiceError as exc:
            sweep.error = exc.detail
            logger.warning(
                "Auto-Hunt for user %s stopped: %s", user_id, exc.detail, extra={"user_id": user_id}
            )
        except Exception:
            sweep.error = INTERRUPTED
            logger.exception("Auto-Hunt for user %s failed", user_id, extra={"user_id": user_id})

        await _record(
            db,
            user_id,
            page=sweep.page,
            companies_added=sweep.companies,
            contacts_found=sweep.contacts,
            error=sweep.error,
        )
        logger.info(
            "Auto-Hunt for user %s: %d companies, %d contacts, next page %d",
            user_id,
            sweep.companies,
            sweep.contacts,
            sweep.page,
            extra={
                "user_id": user_id,
                "companies_added": sweep.companies,
                "contacts_found": sweep.contacts,
                "next_page": sweep.page,
                "error": sweep.error,
            },
        )
