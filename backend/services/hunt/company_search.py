import hashlib
import json
import logging
import os
import re
from typing import Any, Optional
from urllib.parse import quote, unquote, urlsplit

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from services.hunt import apollo, apollo_cache, credits, targets
from services.hunt.apollo import ApolloError
from services.schemas.common import http_url, str_or_none
from services.schemas.company import CompanyFilters, CompanyRow

logger = logging.getLogger(__name__)

MAX_PAGES = 10

_DOMAIN = re.compile(r"(?=.{1,253}$)([a-z0-9-]+\.)+[a-z]{2,63}", re.IGNORECASE)
_LINKEDIN_COMPANY = re.compile(r"/company/([^/?#]+)", re.IGNORECASE)

Page = tuple[list[CompanyRow], int, Optional[int]]

_unsaved_pages: set[tuple[tuple[str, str], ...]] = set()


def warn_if_unconfigured() -> None:
    for name in ("APOLLO_API_KEY", "OPENAI_API_KEY"):
        if not os.getenv(name):
            logger.warning(
                "%s is not set; company search will fail until it is", name, extra={"env_var": name}
            )


def clear_caches() -> None:
    _unsaved_pages.clear()


def _domain(value: Any) -> Optional[str]:
    return value.strip().lower() if isinstance(value, str) and _DOMAIN.fullmatch(value.strip()) else None


def _linkedin_jobs_url(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    url = value.strip() if "://" in value else f"https://{value.strip()}"
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not (
        host == "linkedin.com" or host.endswith(".linkedin.com")
    ):
        return None
    match = _LINKEDIN_COMPANY.match(parts.path)
    if not match:
        return None
    return f"https://www.linkedin.com/company/{quote(unquote(match[1]), safe='-_.')}/jobs/"


def _whole_number(value: Any) -> Optional[int]:
    ok = isinstance(value, int) and not isinstance(value, bool) and value > 0
    return value if ok else None


def to_row(org: dict[str, Any]) -> CompanyRow:
    founded_year = org.get("founded_year")
    return CompanyRow(
        apollo_org_id=org["id"],
        company_name=str_or_none(org.get("name")) or "Unknown",
        domain=_domain(org.get("primary_domain")) or http_url(org.get("website_url")),
        linkedin_url=http_url(org.get("linkedin_url")),
        linkedin_jobs_url=_linkedin_jobs_url(org.get("linkedin_url")),
        logo_url=http_url(org.get("logo_url")),
        founded_year=founded_year
        if isinstance(founded_year, int) and not isinstance(founded_year, bool)
        else None,
        employee_count=_whole_number(org.get("estimated_num_employees")),
    )


def page_store_key(params: list[tuple[str, str]]) -> str:
    return "page:" + hashlib.sha256(json.dumps(params).encode()).hexdigest()


def page_from_store(payload: Any) -> Optional[Page]:
    if payload is None:
        return None
    try:
        rows = [CompanyRow.model_validate(r) for r in payload["rows"]]
        return rows, payload["page_size"], payload["total"]
    except (ValidationError, KeyError, TypeError):
        return None


async def load_page(
    db: AsyncSession,
    filters: CompanyFilters,
    page: int,
    user_id: int,
    params: Optional[list[tuple[str, str]]] = None,
) -> Page:
    store_key = page_store_key(
        params if params is not None else apollo.build_params(filters, page)
    )

    stored = page_from_store(await apollo_cache.get(db, store_key))
    if stored is not None:
        logger.info(
            "Company search page %d from the shared cache, 0 credits",
            page,
            extra={"user_id": user_id, "page": page},
        )
        return stored

    await credits.reserve_credit(db, user_id, f"company search page {page}")
    try:
        companies, page_size, total_entries = await apollo.search_page(filters, page)
    except ApolloError:
        await credits.refund_credit(db, user_id)
        raise
    page_rows = [to_row(org) for org in companies]
    await apollo_cache.put(
        db,
        store_key,
        {
            "rows": [r.model_dump() for r in page_rows],
            "page_size": page_size,
            "total": total_entries,
        },
    )
    return page_rows, page_size, total_entries


def has_more_pages(page: int, page_size: int, total: Optional[int]) -> bool:
    return (
        page_size >= apollo.PER_PAGE
        and page < MAX_PAGES
        and (total is None or page * apollo.PER_PAGE < total)
    )


async def save_page(db: AsyncSession, params: list[tuple[str, str]], rows: list[CompanyRow]) -> None:
    page_key = tuple(params)
    if await targets.save_companies(db, rows):
        _unsaved_pages.discard(page_key)
    else:
        _unsaved_pages.add(page_key)


def needs_saving(params: list[tuple[str, str]]) -> bool:
    return tuple(params) in _unsaved_pages


async def fetch_page(
    db: AsyncSession, filters: CompanyFilters, page: int, user_id: int
) -> tuple[list[CompanyRow], bool]:
    params = apollo.build_params(filters, page)
    rows, page_size, total = await load_page(db, filters, page, user_id, params)
    await save_page(db, params, rows)
    return rows, has_more_pages(page, page_size, total)
