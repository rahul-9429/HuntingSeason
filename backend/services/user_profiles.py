import logging
import zlib
from typing import Any, Optional, get_args

from annotated_types import MaxLen
from pydantic import BaseModel, ValidationError
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from models.user_profile import UserProfile
from services.schemas.user_profile import (
    Education,
    ExperienceItem,
    ExperienceTimeline,
    GeneralInfo,
    Hue,
    Preferences,
    ResumeDetails,
    ResumeEducation,
    ResumeRole,
    TargetLocation,
)

logger = logging.getLogger(__name__)

HUES: tuple[Hue, ...] = get_args(Hue)
MAX_ROLES = 15
MAX_HIGHLIGHTS = 4
MAX_SKILLS = 6


def _hue(company: str) -> Hue:
    return HUES[zlib.crc32(company.lower().encode()) % len(HUES)]


def _fit(model: type[BaseModel], field: str, value: str) -> str:
    value = " ".join(value.split())
    for constraint in model.model_fields[field].metadata:
        if isinstance(constraint, MaxLen):
            return value[: constraint.max_length]
    return value


def _validated(model: type[BaseModel], data: Optional[dict[str, Any]], user_id: int) -> Optional[Any]:
    if not data:
        return None
    try:
        return model.model_validate(data)
    except ValidationError:
        logger.warning("Ignoring unreadable %s for user %s", model.__name__, user_id)
        return None


async def _save(db: AsyncSession, user_id: int, **columns: Any) -> None:
    insert = pg_insert(UserProfile).values(user_id=user_id, **columns)
    await db.execute(
        insert.on_conflict_do_update(
            index_elements=["user_id"], set_={**columns, "updated_at": func.now()}
        )
    )
    await db.commit()


async def get_general(db: AsyncSession, user_id: int) -> GeneralInfo:
    row = await db.get(UserProfile, user_id)
    general = _validated(GeneralInfo, row.general if row else None, user_id) or GeneralInfo()
    if not general.name or not general.email:
        user = await db.get(User, user_id)
        if user is not None:
            general = general.model_copy(
                update={"name": general.name or user.name, "email": general.email or user.email}
            )
    return general


async def update_general(db: AsyncSession, user_id: int, patch: GeneralInfo) -> GeneralInfo:
    current = await get_general(db, user_id)
    merged = current.model_copy(
        update={field: getattr(patch, field) for field in patch.model_fields_set}
    )
    await _save(db, user_id, general=merged.model_dump())
    return merged


async def get_experience(db: AsyncSession, user_id: int) -> ExperienceTimeline:
    row = await db.get(UserProfile, user_id)
    data = (row.experience if row else None) or {}
    roles: list[ResumeRole] = []
    for raw in data.get("roles") or []:
        role = _validated(ResumeRole, raw, user_id)
        if role is not None:
            roles.append(role)
    education = _validated(ResumeEducation, data.get("education"), user_id)
    return ExperienceTimeline(
        items=[
            ExperienceItem(id=str(index), hue=_hue(role.company), **role.model_dump())
            for index, role in enumerate(roles)
        ],
        education=Education(**education.model_dump()) if education else None,
    )


async def get_preferences(db: AsyncSession, user_id: int) -> Preferences:
    row = await db.get(UserProfile, user_id)
    return _validated(Preferences, row.preferences if row else None, user_id) or Preferences()


async def update_preferences(db: AsyncSession, user_id: int, patch: Preferences) -> Preferences:
    current = await get_preferences(db, user_id)
    merged = current.model_copy(
        update={field: getattr(patch, field) for field in patch.model_fields_set}
    )
    await _save(db, user_id, preferences=merged.model_dump())
    return merged


def _general_from_resume(current: GeneralInfo, details: ResumeDetails) -> GeneralInfo:
    found: dict[str, Any] = {
        field: _fit(GeneralInfo, field, getattr(details, field))
        for field in (
            "name",
            "headline",
            "email",
            "phone",
            "location",
            "timezone",
            "linkedin",
            "portfolio",
            "bio",
            "pitch",
            "current_company",
        )
    }
    found["years_experience"] = min(max(details.years_experience, 0), 70)
    return current.model_copy(
        update={field: value for field, value in found.items() if value and not getattr(current, field)}
    )


def _roles_from_resume(details: ResumeDetails) -> list[dict[str, Any]]:
    return [
        ResumeRole(
            role=role.role.strip(),
            company=role.company.strip(),
            start=role.start.strip(),
            end=role.end.strip(),
            location=role.location.strip(),
            highlights=[h.strip() for h in role.highlights if h.strip()][:MAX_HIGHLIGHTS],
            skills=[s.strip() for s in role.skills if s.strip()][:MAX_SKILLS],
        ).model_dump()
        for role in details.roles[:MAX_ROLES]
        if role.role.strip() and role.company.strip()
    ]


def _preferences_from_resume(details: ResumeDetails) -> Preferences:
    locations: list[TargetLocation] = []
    for place in details.target_locations:
        country = place.country.strip()
        city = (place.city or "").strip() or None
        if country and not any(l.country == country and l.city == city for l in locations):
            locations.append(TargetLocation(country=country[:100], city=city[:100] if city else None))
    return Preferences(
        roles=[role.strip() for role in details.target_roles if role.strip()][:3],
        seniority=list(dict.fromkeys(details.target_seniority)),
        locations=locations[:20],
        remote="country" if details.open_to_remote else "none",
    )


async def apply_resume(db: AsyncSession, user_id: int, details: ResumeDetails) -> None:
    row = await db.get(UserProfile, user_id, with_for_update=True)
    general = await get_general(db, user_id)
    columns: dict[str, Any] = {
        "general": _general_from_resume(general, details).model_dump(),
        "experience": {
            "roles": _roles_from_resume(details),
            "education": details.education.model_dump() if details.education else None,
        },
    }
    if row is None or row.preferences is None:
        columns["preferences"] = _preferences_from_resume(details).model_dump()
    await _save(db, user_id, **columns)
