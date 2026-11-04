import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional, cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services.errors import ServiceError
from api.type_models.outreach import AddToOutreachRequest, OutreachCompany, OutreachStatus
from models.company import Company
from models.user_company import UserCompany
from services.hunt import targets
from services.hunt.targets import STUCK_AFTER

ADDS_PER_MINUTE = int(os.getenv("OUTREACH_ADDS_PER_MINUTE", "20"))

_recent_adds: dict[int, deque[float]] = {}


class CompanyNotFound(ServiceError):
    status_code = 404


class TooManyAdds(ServiceError):
    status_code = 429


def clear_caches() -> None:
    _recent_adds.clear()


def _check_add_rate(user_id: int) -> None:
    now = time.monotonic()
    window = _recent_adds.setdefault(user_id, deque())
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= ADDS_PER_MINUTE:
        raise TooManyAdds("Too many companies added at once, wait a minute and try again")
    window.append(now)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def to_outreach_company(target: UserCompany, apollo_org_id: str) -> OutreachCompany:
    stuck = target.status == "searching" and target.searched_at <= _now() - STUCK_AFTER
    return OutreachCompany(
        apollo_org_id=apollo_org_id,
        status=cast(OutreachStatus, "failed" if stuck else target.status),
        contacts_found=target.contacts_found,
        error="The search was interrupted, try again" if stuck else target.error,
        searched_at=target.searched_at,
    )


async def add(
    db: AsyncSession, user_id: int, req: AddToOutreachRequest
) -> tuple[OutreachCompany, Optional[int]]:
    _check_add_rate(user_id)
    company_id = await targets.company_id_for(db, req.apollo_org_id)
    if company_id is None:
        raise CompanyNotFound("We don't know this company yet. Search for it again, then add it.")

    started = await targets.start_search(db, user_id, company_id, req.roles, req.locations)
    target = (
        await db.execute(
            select(UserCompany)
            .where(UserCompany.user_id == user_id, UserCompany.company_id == company_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    await db.commit()
    return to_outreach_company(target, req.apollo_org_id), started


async def list_for(db: AsyncSession, user_id: int) -> list[OutreachCompany]:
    rows = (
        await db.execute(
            select(UserCompany, Company.apollo_org_id)
            .join(Company, Company.id == UserCompany.company_id)
            .where(UserCompany.user_id == user_id)
            .order_by(UserCompany.added_at.desc())
        )
    ).all()
    return [to_outreach_company(target, org_id) for target, org_id in rows]


async def remove(db: AsyncSession, user_id: int, apollo_org_id: str) -> None:
    await db.execute(
        delete(UserCompany).where(
            UserCompany.user_id == user_id,
            UserCompany.company_id
            == select(Company.id).where(Company.apollo_org_id == apollo_org_id).scalar_subquery(),
        )
    )
    await db.commit()
