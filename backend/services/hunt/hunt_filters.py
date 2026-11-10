import hashlib
import json
import logging
from datetime import date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from services import career_profiles, user_profiles
from services.hunt.filters import DEFAULT_JOB_POSTED_WITHIN_DAYS, generate_filters
from services.schemas.career_profile import CareerProfile
from services.schemas.company import CompanyFilters
from services.schemas.user_profile import Culture, Preferences
from services.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 24 * 60 * 60

REMOTE_WORDING = {
    "country": "open to remote roles within the same country",
    "apac": "open to remote roles anywhere in APAC",
    "global": "open to fully remote roles anywhere in the world",
}

_cache: TTLCache[CompanyFilters] = TTLCache(ttl_seconds=CACHE_TTL_SECONDS, max_entries=2000)


def clear_caches() -> None:
    _cache.clear()


def _culture_sentence(culture: Culture) -> Optional[str]:
    parts = []
    if culture.company_stage:
        parts.append(f"at {' or '.join(culture.company_stage)} companies")
    if culture.team_size:
        parts.append(f"with a {culture.team_size} team")
    return " ".join(parts) or None


def describe(preferences: Preferences) -> str:
    roles = ", ".join(preferences.roles)
    seniority = "/".join(preferences.seniority)
    role_phrase = f"{seniority} {roles}".strip() if roles else ""

    places = [
        f"{location.city}, {location.country}" if location.city else location.country
        for location in preferences.locations
    ]

    sentences = []
    if role_phrase:
        where = f" in {' or '.join(places)}" if places else ""
        sentences.append(f"Companies hiring for {role_phrase} roles{where}.")
    elif places:
        sentences.append(f"Companies hiring in {' or '.join(places)}.")

    culture = _culture_sentence(preferences.culture)
    if culture:
        sentences.append(f"Preferably {culture}.")
    remote = REMOTE_WORDING.get(preferences.remote)
    if remote and sentences:
        sentences.append(f"The job seeker is {remote}.")
    return " ".join(sentences)


def _key(description: str, profile: Optional[CareerProfile]) -> str:
    raw = json.dumps(
        [description, profile.model_dump() if profile else None, date.today().year], sort_keys=True
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def filters_key(filters: CompanyFilters) -> str:
    return hashlib.sha256(filters.model_dump_json().encode()).hexdigest()


async def _targets(db: AsyncSession, user_id: int) -> tuple[str, Optional[CareerProfile]]:
    preferences = await user_profiles.get_preferences(db, user_id)
    profile = await career_profiles.get(db, user_id)
    if profile is not None and profile.is_empty():
        profile = None
    return describe(preferences), profile


async def has_targets(db: AsyncSession, user_id: int) -> bool:
    description, profile = await _targets(db, user_id)
    return bool(description) or profile is not None


async def hunt_filters(
    db: AsyncSession, user_id: int
) -> Optional[tuple[CompanyFilters, str]]:
    description, profile = await _targets(db, user_id)
    if not description and profile is None:
        return None

    async def load() -> CompanyFilters:
        return await generate_filters(description, user_id, profile)

    filters, _ = await _cache.get_or_load(_key(description, profile), load)
    if filters.is_empty():
        return None
    if filters.job_posted_within_days is None:
        filters = filters.model_copy(
            update={"job_posted_within_days": DEFAULT_JOB_POSTED_WITHIN_DAYS}
        )
    return filters, filters_key(filters)
