import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import AsyncSessionLocal
from models.company import Company
from models.contact import Contact
from models.user_company import UserCompany
from models.user_contact import UserContact
from services import contact_llm, hunter, tavily, user_profiles
from services.errors import ServiceError
from services.hunt import apollo, apollo_cache, credits, culture, reveal
from services.hunt.credits import CreditLimitReached
from services.hunter import HunterError
from services.schemas.contacts import CONTACT_TYPES, ContactType, WebPerson
from services.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

MAX_CONTACTS = 2
CULTURE_PENALTY = 15
MAX_REFERRER_TITLES = 5

# Titles that match on words but cannot get you hired. A bag-of-words overlap
# scores "Former Engineering Manager" and "Intern, Engineering" as highly as the
# real thing, so each marker subtracts from the score. Matched on whole words,
# which keeps "intern" out of "internal" and "ex" out of "experience".
TITLE_DEMOTIONS = {
    "former": 30,
    "ex": 30,
    "retired": 30,
    "intern": 25,
    "internship": 25,
    "trainee": 25,
    "student": 25,
    "apprentice": 20,
    "volunteer": 20,
    "freelance": 10,
    "freelancer": 10,
    "contractor": 10,
}
# Phrases need the raw string: "assistant to the VP" is not "VP".
PHRASE_DEMOTIONS = (("assistant to", 20), ("executive assistant", 20))
# A title is demoted, never buried: the floor keeps a weak signal from
# outranking someone we know nothing about.
MAX_DEMOTION = 40
MAX_WEB_TITLES = 4
SEARCHES_AT_ONCE = 4

RECRUITER_TITLES = [
    "recruiter",
    "technical recruiter",
    "talent acquisition",
    "talent acquisition manager",
    "head of talent",
    "hr business partner",
]
LEADERSHIP_TITLES = ["founder", "co-founder", "ceo", "managing director", "general manager"]
RECRUITER_WORDS = {"recruiter", "recruiting", "recruitment", "talent"}

HUNTER_BASE_DEPARTMENTS = {"executive", "hr", "management"}
HUNTER_DEPARTMENTS = {
    "it": {"engineer", "engineering", "developer", "software", "devops", "data", "backend",
           "frontend", "fullstack", "qa", "security", "sre", "architect", "it"},
    "sales": {"sales", "account", "bdr", "sdr"},
    "marketing": {"marketing", "growth", "seo", "content", "brand"},
    "design": {"design", "designer", "ux", "ui"},
    "product": {"product"},
    "finance": {"finance", "financial", "accountant", "accounting"},
    "operations": {"operations", "ops", "logistics", "supply"},
    "support": {"support", "customer", "success"},
    "legal": {"legal", "lawyer", "counsel", "compliance"},
}

_WORD = re.compile(r"[a-z0-9+#]+")

_manager_titles_cache: TTLCache[list[str]] = TTLCache(ttl_seconds=24 * 60 * 60, max_entries=2000)
_searches = asyncio.Semaphore(SEARCHES_AT_ONCE)


@dataclass
class Candidate:
    person: dict[str, Any]
    type: ContactType
    relevance: int
    source: str = "apollo"


def clear_caches() -> None:
    _manager_titles_cache.clear()


def _words(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


async def _manager_titles(roles: list[str], user_id: int) -> list[str]:
    key = tuple(sorted(" ".join(r.lower().split()) for r in roles))
    try:
        titles, _ = await _manager_titles_cache.get_or_load(
            key, lambda: contact_llm.hiring_manager_titles(roles, user_id)
        )
    except ServiceError as exc:
        logger.warning(
            "Falling back to leadership titles: %s", exc.detail, extra={"user_id": user_id}
        )
        return LEADERSHIP_TITLES
    return titles or LEADERSHIP_TITLES


async def titles_by_type(roles: list[str], user_id: int) -> dict[ContactType, list[str]]:
    if not roles:
        return {"hiring_manager": LEADERSHIP_TITLES, "recruiter": RECRUITER_TITLES}
    return {
        "hiring_manager": await _manager_titles(roles, user_id),
        "recruiter": RECRUITER_TITLES,
        "referrer": roles[:MAX_REFERRER_TITLES],
    }


def _slim_person(person: dict[str, Any]) -> Optional[dict[str, Any]]:
    person_id, first_name = person.get("id"), person.get("first_name")
    if not isinstance(person_id, str) or not isinstance(first_name, str) or not first_name:
        return None
    title, last = person.get("title"), person.get("last_name_obfuscated")
    return {
        "id": person_id,
        "first_name": first_name,
        "last_name_obfuscated": last if isinstance(last, str) and last else None,
        "title": title if isinstance(title, str) and title else None,
        "has_email": person.get("has_email") is True,
    }


async def _people(
    db: AsyncSession, org_id: str, titles: list[str], locations: list[str]
) -> list[dict[str, Any]]:
    request = [org_id, sorted(t.lower() for t in titles), sorted(loc.lower() for loc in locations)]
    store_key = "people:" + hashlib.sha256(json.dumps(request).encode()).hexdigest()
    stored = await apollo_cache.get(db, store_key)
    if isinstance(stored, list):
        return stored

    found = await apollo.search_people(org_id, titles, locations)
    people = [p for p in map(_slim_person, found) if p is not None]
    await apollo_cache.put(db, store_key, people)
    return people


def _overlap(title: Optional[str], titles: list[str]) -> float:
    words = _words(title or "")
    return max(
        (len(wanted & words) / len(wanted) for wanted in map(_words, titles) if wanted),
        default=0.0,
    )


def demotion(title: Optional[str]) -> int:
    """How much a title's own wording argues against contacting this person."""
    if not title:
        return 0
    found = _words(title)
    points = sum(points for word, points in TITLE_DEMOTIONS.items() if word in found)
    flattened = " ".join(title.casefold().split())
    points += sum(points for phrase, points in PHRASE_DEMOTIONS if phrase in flattened)
    return min(points, MAX_DEMOTION)


def relevance(
    title: Optional[str],
    titles: list[str],
    has_email: bool,
    in_location: bool,
    fits_culture: bool = True,
) -> int:
    # Positive: a floor everyone gets, how well the title matches, and whether we
    # can actually reach them. Negative: the title's own disqualifiers, and a
    # company whose culture does not fit what the user asked for.
    score = 30 + 40 * _overlap(title, titles) + 15 * has_email + 15 * in_location
    score -= demotion(title)
    score -= 0 if fits_culture else CULTURE_PENALTY
    return max(0, round(score))


def hunter_departments(roles: list[str]) -> list[str]:
    words = set().union(*map(_words, roles)) if roles else set()
    found = {dept for dept, keys in HUNTER_DEPARTMENTS.items() if words & keys}
    return sorted(HUNTER_BASE_DEPARTMENTS | found)


async def _hunter_people(
    db: AsyncSession, domain: str, departments: list[str], user_id: int
) -> tuple[list[dict[str, Any]], bool]:
    store_key = "hunter:" + hashlib.sha256(json.dumps([domain, departments]).encode()).hexdigest()
    stored = await apollo_cache.get(db, store_key)
    if isinstance(stored, list):
        return stored, False

    fields = {"user_id": user_id, "domain": domain}
    try:
        await credits.reserve_credit(db, user_id, f"Hunter search for {domain}")
    except CreditLimitReached:
        logger.info("Skipping Hunter for %s: no credits left", domain, extra=fields)
        return [], False
    try:
        people = await hunter.domain_search(domain, departments)
    except HunterError as exc:
        await credits.refund_credit(db, user_id)
        logger.warning("Hunter search for %s failed: %s", domain, exc.detail, extra=fields)
        return [], False
    if not people:
        await credits.refund_credit(db, user_id)
    await apollo_cache.put(db, store_key, people)
    return people, bool(people)


def type_by_title(
    person: dict[str, Any],
    titles: dict[ContactType, list[str]],
    fits_culture: bool = True,
) -> Optional[tuple[ContactType, int]]:
    kind: Optional[ContactType] = None
    if person.get("department") == "hr" or _words(person.get("title") or "") & RECRUITER_WORDS:
        kind = "recruiter"
    else:
        best = 0.0
        for candidate_kind in ("hiring_manager", "referrer"):
            overlap = _overlap(person.get("title"), titles.get(candidate_kind, []))
            if overlap > best:
                kind, best = candidate_kind, overlap
        if kind is None and (
            person.get("seniority") == "executive"
            or person.get("department") in ("executive", "management")
        ):
            kind = "hiring_manager"
    if kind is None:
        return None
    has_email = person.get("email") is not None
    return kind, relevance(
        person.get("title"), titles.get(kind, []), has_email, False, fits_culture
    )


def same_person(found: dict[str, Any], apollo_person: dict[str, Any]) -> bool:
    if found["first_name"].casefold() != apollo_person["first_name"].casefold():
        return False
    last = (found.get("last_name") or "").casefold()
    hidden = (apollo_person.get("last_name_obfuscated") or "").casefold()
    if "*" not in hidden:
        return last == hidden
    head, tail = hidden.split("*", 1)[0], hidden.rsplit("*", 1)[1]
    return last.startswith(head) and last.endswith(tail)


def _already_picked(person: dict[str, Any], picked: list[Candidate]) -> bool:
    full_name = (person["first_name"].casefold(), (person.get("last_name") or "").casefold())
    for c in picked:
        if c.source == "apollo":
            if same_person(person, c.person):
                return True
        elif (c.person["first_name"].casefold(), (c.person.get("last_name") or "").casefold()) == full_name:
            return True
    return False


def _choose(
    people: list[dict[str, Any]],
    source: str,
    titles: dict[ContactType, list[str]],
    picked: list[Candidate],
    fits_culture: bool = True,
) -> list[Candidate]:
    found: list[Candidate] = []
    for person in people:
        if _already_picked(person, picked):
            continue
        typed = type_by_title(person, titles, fits_culture)
        if typed is not None:
            found.append(Candidate(person, typed[0], typed[1], source=source))
    found.sort(key=lambda c: c.relevance, reverse=True)

    have = {c.type for c in picked}
    room = MAX_CONTACTS - len(picked)
    fill: list[Candidate] = []
    for kind in CONTACT_TYPES:
        best = next((c for c in found if c.type == kind), None)
        if len(fill) < room and kind not in have and best is not None:
            fill.append(best)
            have.add(kind)
    fill.extend(c for c in found if c not in fill)
    return fill[:room]


async def _hunter_fill(
    db: AsyncSession,
    domain: Optional[str],
    roles: list[str],
    titles: dict[ContactType, list[str]],
    picked: list[Candidate],
    user_id: int,
    fits_culture: bool = True,
) -> list[Candidate]:
    if not domain or not hunter.configured():
        return []
    people, charged = await _hunter_people(db, domain, hunter_departments(roles), user_id)
    chosen = _choose(people, "hunter", titles, picked, fits_culture)
    if charged and not chosen:
        await credits.refund_credit(db, user_id)
    return chosen


def verified_web_people(found: list[WebPerson], results: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_url = {r["url"].strip(): r for r in results}
    people: list[dict[str, Any]] = []
    seen: set[str] = set()
    for person in found:
        result = by_url.get(person.url.strip())
        linkedin = tavily.linkedin_profile(person.url)
        names = person.name.split()
        title = " ".join(person.title.split())
        if result is None or linkedin is None or linkedin in seen or len(names) < 2:
            continue
        if not title or len(title) > 100:
            continue
        text = f"{result['title']} {result['content']}".casefold()
        if not all(name.casefold() in text for name in names):
            continue
        seen.add(linkedin)
        people.append(
            {
                "first_name": names[0],
                "last_name": " ".join(names[1:]),
                "title": title,
                "linkedin_url": linkedin,
                "email": None,
            }
        )
    return people


def _web_titles(titles: dict[ContactType, list[str]], picked: list[Candidate]) -> list[str]:
    have = {c.type for c in picked}
    kinds = [kind for kind in titles if kind not in have] or list(titles)
    wanted: list[str] = []
    for i in range(max(map(len, titles.values()), default=0)):
        wanted.extend(titles[kind][i] for kind in kinds if i < len(titles[kind]))
    return list(dict.fromkeys(wanted))[:MAX_WEB_TITLES]


async def _web_people(
    db: AsyncSession,
    company: str,
    domain: str,
    titles: list[str],
    locations: list[str],
    user_id: int,
) -> tuple[list[dict[str, Any]], bool]:
    request = [domain, sorted(t.lower() for t in titles), sorted(loc.lower() for loc in locations)]
    store_key = "tavily:" + hashlib.sha256(json.dumps(request).encode()).hexdigest()
    stored = await apollo_cache.get(db, store_key)
    if isinstance(stored, list):
        return stored, False

    fields = {"user_id": user_id, "domain": domain}
    try:
        await credits.reserve_credit(db, user_id, f"web search for {domain}")
    except CreditLimitReached:
        logger.info("Skipping web search for %s: no credits left", domain, extra=fields)
        return [], False
    query = " ".join([f'"{company}"', " OR ".join(f'"{t}"' for t in titles), *locations[:1]])
    try:
        results = await tavily.search(query, ["linkedin.com"])
        found = await contact_llm.web_people(company, domain, titles, results, user_id) if results else []
    except ServiceError as exc:
        await credits.refund_credit(db, user_id)
        logger.warning("Web search for %s failed: %s", domain, exc.detail, extra=fields)
        return [], False
    people = verified_web_people(found, results)
    if not people:
        await credits.refund_credit(db, user_id)
    await apollo_cache.put(db, store_key, people)
    return people, bool(people)


async def _web_fill(
    db: AsyncSession,
    company: Optional[str],
    domain: Optional[str],
    locations: list[str],
    titles: dict[ContactType, list[str]],
    picked: list[Candidate],
    user_id: int,
    fits_culture: bool = True,
) -> list[Candidate]:
    if not company or not domain or not tavily.configured():
        return []
    people, charged = await _web_people(
        db, company, domain, _web_titles(titles, picked), locations, user_id
    )
    chosen = _choose(people, "tavily", titles, picked, fits_culture)
    if charged and not chosen:
        await credits.refund_credit(db, user_id)
    for candidate in chosen:
        candidate.person = {**candidate.person, "email": await _verified_web_email(candidate.person, domain)}
    return chosen


async def _verified_web_email(person: dict[str, Any], domain: str) -> Optional[str]:
    if not hunter.configured():
        return None
    try:
        return await hunter.find_email(domain, person["first_name"], person["last_name"])
    except HunterError as exc:
        logger.warning(
            "Hunter email lookup for a web contact failed: %s", exc.detail, extra={"domain": domain}
        )
        return None


async def find_candidates(
    db: AsyncSession,
    org_id: str,
    roles: list[str],
    locations: list[str],
    user_id: int,
    domain: Optional[str] = None,
    company: Optional[str] = None,
    fits_culture: bool = True,
) -> list[Candidate]:
    titles_wanted = await titles_by_type(roles, user_id)
    picked: list[Candidate] = []
    spare: list[Candidate] = []
    taken: set[str] = set()
    for kind, titles in titles_wanted.items():
        if len(picked) >= MAX_CONTACTS:
            break
        found: dict[str, tuple[dict[str, Any], bool]] = {}
        if locations:
            for person in await _people(db, org_id, titles, locations):
                found.setdefault(person["id"], (person, True))
        if not found:
            for person in await _people(db, org_id, titles, []):
                found.setdefault(person["id"], (person, False))

        scored = [
            Candidate(
                person,
                kind,
                relevance(
                    person["title"], titles, person["has_email"], in_location, fits_culture
                ),
            )
            for person, in_location in found.values()
            if person["id"] not in taken
        ]
        scored.sort(key=lambda c: c.relevance, reverse=True)
        if scored:
            picked.append(scored[0])
            taken.add(scored[0].person["id"])
            spare.extend(scored[1:])

    spare.sort(key=lambda c: c.relevance, reverse=True)
    for candidate in spare:
        if len(picked) >= MAX_CONTACTS:
            break
        if candidate.person["id"] not in taken:
            picked.append(candidate)
            taken.add(candidate.person["id"])

    if len(picked) < MAX_CONTACTS:
        picked.extend(
            await _hunter_fill(db, domain, roles, titles_wanted, picked, user_id, fits_culture)
        )
    if len(picked) < MAX_CONTACTS:
        picked.extend(
            await _web_fill(
                db, company, domain, locations, titles_wanted, picked, user_id, fits_culture
            )
        )

    order = {kind: i for i, kind in enumerate(CONTACT_TYPES)}
    picked.sort(key=lambda c: order[c.type])
    return picked


def _key(candidate: Candidate) -> str:
    if candidate.source == "hunter":
        return candidate.person["email"]
    if candidate.source == "tavily":
        return candidate.person["linkedin_url"]
    return candidate.person["id"]


async def _save_apollo(
    db: AsyncSession, company_id: int, candidates: list[Candidate]
) -> tuple[dict[str, int], list[int]]:
    if not candidates:
        return {}, []
    insert = pg_insert(Contact).values(
        [
            {
                "source": "apollo",
                "apollo_person_id": c.person["id"],
                "company_id": company_id,
                "first_name": c.person["first_name"],
                "last_name_obfuscated": c.person["last_name_obfuscated"],
                "title": c.person["title"],
                "has_email": c.person["has_email"],
            }
            for c in candidates
        ]
    )
    saved = await db.execute(
        insert.on_conflict_do_update(
            index_elements=["apollo_person_id"],
            set_={
                "company_id": insert.excluded.company_id,
                "last_name_obfuscated": func.coalesce(
                    Contact.last_name_obfuscated, insert.excluded.last_name_obfuscated
                ),
                "title": func.coalesce(Contact.title, insert.excluded.title),
                "has_email": or_(Contact.has_email, insert.excluded.has_email),
            },
        ).returning(Contact.id, Contact.apollo_person_id, Contact.revealed_at)
    )
    rows = saved.all()
    unrevealed = [contact_id for contact_id, _, revealed_at in rows if revealed_at is None]
    return {person_id: contact_id for contact_id, person_id, _ in rows}, unrevealed


async def _save_hunter(
    db: AsyncSession, company_id: int, candidates: list[Candidate]
) -> dict[str, int]:
    if not candidates:
        return {}
    insert = pg_insert(Contact).values(
        [
            {
                "source": "hunter",
                "company_id": company_id,
                "first_name": c.person["first_name"],
                "last_name": c.person["last_name"],
                "title": c.person["title"],
                "seniority": c.person["seniority"],
                "has_email": True,
                "email": c.person["email"],
                "email_status": "valid",
                "email_source": "hunter",
                "linkedin_url": c.person["linkedin_url"],
                "revealed_at": func.now(),
            }
            for c in candidates
        ]
    )
    saved = await db.execute(
        insert.on_conflict_do_update(
            index_elements=["email"],
            index_where=text("source = 'hunter'"),
            set_={
                "company_id": insert.excluded.company_id,
                "title": func.coalesce(Contact.title, insert.excluded.title),
                "linkedin_url": func.coalesce(Contact.linkedin_url, insert.excluded.linkedin_url),
            },
        ).returning(Contact.id, Contact.email)
    )
    return {email: contact_id for contact_id, email in saved.all()}


async def _save_tavily(
    db: AsyncSession, company_id: int, candidates: list[Candidate]
) -> dict[str, int]:
    if not candidates:
        return {}
    insert = pg_insert(Contact).values(
        [
            {
                "source": "tavily",
                "company_id": company_id,
                "first_name": c.person["first_name"],
                "last_name": c.person["last_name"],
                "title": c.person["title"],
                "has_email": c.person["email"] is not None,
                "email": c.person["email"],
                "email_status": "valid" if c.person["email"] else None,
                "email_source": "hunter" if c.person["email"] else None,
                "linkedin_url": c.person["linkedin_url"],
                "revealed_at": func.now(),
            }
            for c in candidates
        ]
    )
    saved = await db.execute(
        insert.on_conflict_do_update(
            index_elements=["linkedin_url"],
            index_where=text("source = 'tavily'"),
            set_={
                "company_id": insert.excluded.company_id,
                "title": func.coalesce(Contact.title, insert.excluded.title),
                "email": func.coalesce(Contact.email, insert.excluded.email),
                "email_status": func.coalesce(Contact.email_status, insert.excluded.email_status),
                "email_source": func.coalesce(Contact.email_source, insert.excluded.email_source),
                "has_email": or_(Contact.has_email, insert.excluded.has_email),
            },
        ).returning(Contact.id, Contact.linkedin_url)
    )
    return {linkedin: contact_id for contact_id, linkedin in saved.all()}


async def _save(
    db: AsyncSession, user_id: int, user_company_id: int, company_id: int, candidates: list[Candidate]
) -> tuple[int, list[int]]:
    unrevealed: list[int] = []
    if candidates:
        apollo_ids, unrevealed = await _save_apollo(
            db, company_id, [c for c in candidates if c.source == "apollo"]
        )
        contact_ids = {
            **apollo_ids,
            **await _save_hunter(db, company_id, [c for c in candidates if c.source == "hunter"]),
            **await _save_tavily(db, company_id, [c for c in candidates if c.source == "tavily"]),
        }
        await db.execute(
            pg_insert(UserContact)
            .values(
                [
                    {
                        "user_id": user_id,
                        "contact_id": contact_ids[_key(c)],
                        "user_company_id": user_company_id,
                        "type": c.type,
                        "relevance": c.relevance,
                    }
                    for c in candidates
                ]
            )
            .on_conflict_do_nothing(index_elements=["user_id", "contact_id"])
        )
    found = (
        await db.execute(
            select(func.count())
            .select_from(UserContact)
            .where(UserContact.user_company_id == user_company_id)
        )
    ).scalar_one()
    return found, unrevealed


async def reveal_found(
    db: AsyncSession, user_id: int, contact_ids: list[int], domain: Optional[str]
) -> int:
    revealed = 0
    fields = {"user_id": user_id, "domain": domain}
    for contact_id in contact_ids:
        try:
            await reveal.reveal_contact(db, user_id, contact_id, domain)
        except CreditLimitReached:
            logger.info("No credits left to reveal new contacts", extra=fields)
            break
        except ServiceError as exc:
            logger.warning(
                "Couldn't reveal contact %s: %s",
                contact_id,
                exc.detail,
                extra={**fields, "contact_id": contact_id},
            )
            continue
        except Exception:
            logger.exception(
                "Couldn't reveal contact %s", contact_id, extra={**fields, "contact_id": contact_id}
            )
            continue
        revealed += 1
    return revealed


async def find_contacts(user_company_id: int) -> None:
    async with _searches, AsyncSessionLocal() as db:
        user_id: Optional[int] = None
        org_id: Optional[str] = None
        found, error = 0, None
        try:
            target = await db.get(UserCompany, user_company_id)
            if target is None or target.status != "searching":
                return
            user_id, company_id = target.user_id, target.company_id
            roles, locations = target.roles, target.locations
            org_id, domain, company_name, employee_count = (
                await db.execute(
                    select(
                        Company.apollo_org_id,
                        Company.domain,
                        Company.name,
                        Company.employee_count,
                    ).where(Company.id == company_id)
                )
            ).one()

            preferences = await user_profiles.get_preferences(db, user_id)
            fits_culture = culture.fits(preferences.culture.company_stage, employee_count)
            bare = hunter.bare_domain(domain)
            candidates = await find_candidates(
                db, org_id, roles, locations, user_id, bare, company_name, fits_culture
            )
            found, unrevealed = await _save(db, user_id, user_company_id, company_id, candidates)
            await db.commit()
            await reveal_found(db, user_id, unrevealed, bare)
        except ServiceError as exc:
            await db.rollback()
            error = exc.detail
        except Exception:
            await db.rollback()
            logger.exception(
                "Contact search for user company %s failed",
                user_company_id,
                extra={"user_id": user_id, "org_id": org_id, "user_company_id": user_company_id},
            )
            error = "Couldn't find contacts, try again"

        status = "failed" if error else "ready" if found else "no_contacts"
        try:
            await db.execute(
                update(UserCompany)
                .where(UserCompany.id == user_company_id, UserCompany.status == "searching")
                .values(status=status, contacts_found=found, error=error)
            )
            await db.commit()
        except Exception:
            logger.exception(
                "Couldn't record the contact search result",
                extra={"user_id": user_id, "org_id": org_id, "user_company_id": user_company_id},
            )
            return
        logger.info(
            "Contact search for %s (user %s): %s, %d contacts",
            org_id,
            user_id,
            status,
            found,
            extra={
                "user_id": user_id,
                "org_id": org_id,
                "user_company_id": user_company_id,
                "search_status": status,
                "contacts_found": found,
                "error": error,
            },
        )
