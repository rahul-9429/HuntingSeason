import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.company import Company
from models.user_company import UserCompany
from services.schemas.company import CompanyRow

logger = logging.getLogger(__name__)

STUCK_AFTER = timedelta(minutes=10)
RETRY_NO_CONTACTS_AFTER = timedelta(days=30)


def _text(value: Optional[str]) -> Optional[str]:
    return value.replace("\x00", "") if value else value


async def save_companies(db: AsyncSession, rows: list[CompanyRow]) -> bool:
    by_id = {r.apollo_org_id: r for r in rows}
    if not by_id:
        return True
    insert = pg_insert(Company).values(
        [
            {
                "apollo_org_id": org_id,
                "name": _text(r.company_name) or "Unknown",
                "domain": _text(r.domain),
                "linkedin_url": _text(r.linkedin_url),
                "linkedin_jobs_url": _text(r.linkedin_jobs_url),
                "logo_url": _text(r.logo_url),
                "founded_year": r.founded_year
                if r.founded_year is not None and 0 < r.founded_year < 10_000
                else None,
                "employee_count": r.employee_count,
            }
            for org_id, r in sorted(by_id.items())
        ]
    )
    try:
        await db.execute(
            insert.on_conflict_do_update(
                index_elements=["apollo_org_id"],
                set_={
                    **{
                        col: insert.excluded[col]
                        for col in (
                            "name",
                            "domain",
                            "linkedin_url",
                            "linkedin_jobs_url",
                            "logo_url",
                            "founded_year",
                        )
                    },
                    "employee_count": func.coalesce(
                        insert.excluded.employee_count, Company.employee_count
                    ),
                    "updated_at": func.now(),
                },
            )
        )
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Couldn't save %d companies", len(by_id), extra={"companies": len(by_id)})
        return False
    return True


async def company_id_for(db: AsyncSession, apollo_org_id: str) -> Optional[int]:
    return (
        await db.execute(select(Company.id).where(Company.apollo_org_id == apollo_org_id))
    ).scalar_one_or_none()


async def start_search(
    db: AsyncSession, user_id: int, company_id: int, roles: list[str], locations: list[str]
) -> Optional[int]:
    search = {"roles": roles, "locations": locations, "status": "searching", "error": None}
    started = (
        await db.execute(
            pg_insert(UserCompany)
            .values(user_id=user_id, company_id=company_id, **search)
            .on_conflict_do_nothing(index_elements=["user_id", "company_id"])
            .returning(UserCompany.id)
        )
    ).scalar_one_or_none()
    if started is not None:
        return started
    return (
        await db.execute(
            update(UserCompany)
            .where(
                UserCompany.user_id == user_id,
                UserCompany.company_id == company_id,
                or_(
                    UserCompany.status == "failed",
                    and_(
                        UserCompany.status == "searching",
                        UserCompany.searched_at <= func.now() - STUCK_AFTER,
                    ),
                    and_(
                        UserCompany.status == "no_contacts",
                        UserCompany.searched_at <= func.now() - RETRY_NO_CONTACTS_AFTER,
                    ),
                ),
            )
            .values(**search, contacts_found=0, searched_at=func.now())
            .returning(UserCompany.id)
        )
    ).scalar_one_or_none()
