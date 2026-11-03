import hashlib
import logging
import os
import re
import time
from collections import deque
from datetime import date
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services.errors import ServiceError
from api.type_models.company_search import (
    MAX_ITEMS,
    MAX_TEXT_LENGTH,
    CompanyFilters,
    CompanyRow,
    CompanySearchRequest,
    CompanySearchResponse,
    JobPosting,
    JobPostingsResponse,
)
from services import career_profiles
from services.hunt import apollo, apollo_cache, company_search, credits
from services.hunt.apollo import ApolloError
from services.hunt.company_search import MAX_PAGES, Page
from services.hunt.filters import (
    DEFAULT_JOB_POSTED_WITHIN_DAYS,
    FilterGenerationError,
    generate_filters,
)
from services.schemas.career_profile import CareerProfile
from services.schemas.common import http_url, str_or_none
from services.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

MAX_POSTINGS_RETURNED = 50
NEW_SEARCHES_PER_MINUTE = int(os.getenv("COMPANY_SEARCHES_PER_MINUTE", "10"))

_filters_cache: TTLCache[CompanyFilters] = TTLCache(ttl_seconds=60 * 60, max_entries=2000)
_pages_cache: TTLCache[Page] = TTLCache(ttl_seconds=60 * 60, max_entries=500)
_postings_cache: TTLCache[list[dict[str, Optional[str]]]] = TTLCache(
    ttl_seconds=6 * 60 * 60, max_entries=1000
)
_recent_searches: dict[int, deque[float]] = {}

_WORD = re.compile(r"[a-z0-9+#]+")

Postings = list[dict[str, Optional[str]]]

warn_if_unconfigured = company_search.warn_if_unconfigured
to_row = company_search.to_row


class TooManySearches(ServiceError):
    status_code = 429


def clear_caches() -> None:
    _filters_cache.clear()
    _pages_cache.clear()
    _postings_cache.clear()
    _recent_searches.clear()
    company_search.clear_caches()


def _check_search_rate(user_id: int) -> None:
    now = time.monotonic()
    window = _recent_searches.setdefault(user_id, deque())
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= NEW_SEARCHES_PER_MINUTE:
        raise TooManySearches("Too many new searches, wait a minute and try again")
    window.append(now)


def _profile_key(profile: Optional[CareerProfile]) -> Optional[str]:
    if profile is None:
        return None
    return hashlib.sha256(profile.model_dump_json().encode()).hexdigest()


async def _filters_for(
    query: str, user_id: int, profile: Optional[CareerProfile]
) -> CompanyFilters:
    async def load() -> CompanyFilters:
        _check_search_rate(user_id)
        return await generate_filters(query, user_id, profile)

    key = (" ".join(query.lower().split()), date.today().year, _profile_key(profile))
    filters, _ = await _filters_cache.get_or_load(key, load)
    return filters


async def search(
    req: CompanySearchRequest, user_id: int, db: AsyncSession
) -> CompanySearchResponse:
    query = req.query.strip()
    profile = None
    if req.use_profile and req.filters is None:
        profile = await career_profiles.get(db, user_id)
        if profile is not None and profile.is_empty():
            profile = None
    if not query and profile is None and req.filters is None:
        raise FilterGenerationError("Describe the companies you're looking for")

    filters = req.filters or await _filters_for(query, user_id, profile)
    if filters.is_empty():
        raise FilterGenerationError(
            "Couldn't find anything to search on. Try naming a role, location or industry."
        )
    if filters.job_posted_within_days is None:
        filters = filters.model_copy(
            update={"job_posted_within_days": DEFAULT_JOB_POSTED_WITHIN_DAYS}
        )

    rows: list[CompanyRow] = []
    total: Optional[int] = None
    has_more = False
    if req.page <= MAX_PAGES:
        params = apollo.build_params(filters, req.page)

        async def load() -> Page:
            return await company_search.load_page(db, filters, req.page, user_id, params)

        page_key = tuple(params)
        (rows, page_size, total), loaded = await _pages_cache.get_or_load(page_key, load)
        if loaded or company_search.needs_saving(params):
            await company_search.save_page(db, params, rows)
        has_more = company_search.has_more_pages(req.page, page_size, total)

    return CompanySearchResponse(
        query=query,
        filters=filters,
        page=req.page,
        rows=rows,
        total_entries=total,
        has_more=has_more,
        credits_left=await credits.credits_left(db, user_id),
        used_profile=profile is not None,
    )


def _words(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _location(posting: dict[str, Any]) -> Optional[str]:
    parts = [posting.get(key) for key in ("city", "state", "country")]
    return ", ".join(p for p in parts if isinstance(p, str) and p) or None


def _slim_posting(posting: dict[str, Any]) -> dict[str, Optional[str]]:
    return {
        "title": str_or_none(posting.get("title")),
        "url": http_url(posting.get("url")),
        "location": _location(posting),
        "posted_at": str_or_none(posting.get("posted_at")),
    }


async def job_postings(
    org_id: str, roles: list[str], user_id: int, db: AsyncSession
) -> JobPostingsResponse:
    store_key = f"postings:{org_id}"

    async def load() -> Postings:
        stored = await apollo_cache.get(db, store_key)
        if isinstance(stored, list):
            logger.info(
                "Job postings for %s from the shared cache, 0 credits",
                org_id,
                extra={"user_id": user_id, "org_id": org_id},
            )
            return stored

        await credits.reserve_credit(db, user_id, f"job postings for {org_id}")
        try:
            raw = await apollo.get_job_postings(org_id)
        except ApolloError:
            await credits.refund_credit(db, user_id)
            raise
        slim = [_slim_posting(p) for p in raw]
        await apollo_cache.put(db, store_key, slim)
        return slim

    stored, _ = await _postings_cache.get_or_load(org_id, load)

    roles = [r for r in roles if len(r) <= MAX_TEXT_LENGTH][:MAX_ITEMS]
    role_words = [words for words in (_words(r) for r in roles) if words]
    postings = []
    for p in stored:
        if not isinstance(p, dict):
            continue
        title = p.get("title") or "Untitled role"
        title_words = _words(title)
        postings.append(
            JobPosting(
                title=title,
                url=p.get("url"),
                location=p.get("location"),
                posted_at=p.get("posted_at"),
                matches_role=any(words <= title_words for words in role_words),
            )
        )

    postings.sort(key=lambda p: p.posted_at or "", reverse=True)
    postings.sort(key=lambda p: not p.matches_role)
    return JobPostingsResponse(
        org_id=org_id,
        postings=postings[:MAX_POSTINGS_RETURNED],
        matched_count=sum(p.matches_role for p in postings),
        total=len(postings),
        credits_left=await credits.credits_left(db, user_id),
    )
