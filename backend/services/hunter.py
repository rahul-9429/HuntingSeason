import logging
import os
from typing import Any, Optional
from urllib.parse import urlsplit

import httpx

from services.errors import ServiceError
from services.schemas.common import http_url, str_or_none

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 50
DOMAIN_SEARCH_LIMIT = 10

_client = httpx.AsyncClient(base_url="https://api.hunter.io/v2", timeout=20)


class HunterError(ServiceError):
    status_code = 502


def configured() -> bool:
    return bool(os.getenv("HUNTER_API_KEY"))


def bare_domain(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    host = urlsplit(value if "://" in value else f"https://{value}").hostname or ""
    return host.removeprefix("www.") or None


def warn_if_unconfigured() -> None:
    if not configured():
        logger.warning(
            "HUNTER_API_KEY is not set; contact search uses Apollo only",
            extra={"env_var": "HUNTER_API_KEY"},
        )


async def close_client() -> None:
    await _client.aclose()


async def _get(path: str, endpoint_name: str, params: list[tuple[str, str]]) -> dict[str, Any]:
    api_key = os.getenv("HUNTER_API_KEY")
    if not api_key:
        raise HunterError("HUNTER_API_KEY is not set", status_code=500)
    try:
        response = await _client.get(path, params=tuple(params), headers={"X-API-KEY": api_key})
    except httpx.HTTPError as exc:
        raise HunterError(f"Couldn't reach Hunter {endpoint_name}") from exc

    if response.status_code == 401:
        raise HunterError("Hunter rejected HUNTER_API_KEY")
    if response.status_code in (403, 429):
        raise HunterError(f"Hunter {endpoint_name} limit reached", status_code=429)
    if response.is_error:
        logger.warning(
            "Hunter %s returned %s: %s",
            endpoint_name,
            response.status_code,
            response.text[:500],
            extra={"hunter_endpoint": endpoint_name, "status_code": response.status_code},
        )
        raise HunterError(f"Hunter {endpoint_name} failed ({response.status_code})")

    try:
        data = response.json().get("data")
    except (ValueError, AttributeError) as exc:
        raise HunterError(f"Hunter {endpoint_name} returned an unreadable response") from exc
    return data if isinstance(data, dict) else {}


def verified_email(email: Any, confidence: Any, verification: Any) -> Optional[str]:
    status = verification.get("status") if isinstance(verification, dict) else None
    if (
        isinstance(email, str)
        and "@" in email
        and isinstance(confidence, int)
        and confidence >= MIN_CONFIDENCE
        and status == "valid"
    ):
        return email.strip().lower()
    return None


def _person(entry: dict[str, Any]) -> Optional[dict[str, Any]]:
    email = verified_email(entry.get("value"), entry.get("confidence"), entry.get("verification"))
    first_name = str_or_none(entry.get("first_name"))
    if email is None or first_name is None or entry.get("type") == "generic":
        return None
    return {
        "email": email,
        "first_name": first_name,
        "last_name": str_or_none(entry.get("last_name")),
        "title": str_or_none(entry.get("position")),
        "seniority": str_or_none(entry.get("seniority")),
        "department": str_or_none(entry.get("department")),
        "linkedin_url": http_url(entry.get("linkedin")),
    }


async def domain_search(domain: str, departments: list[str]) -> list[dict[str, Any]]:
    params = [
        ("domain", domain),
        ("type", "personal"),
        ("limit", str(DOMAIN_SEARCH_LIMIT)),
        ("required_field", "full_name,position"),
        ("verification_status", "valid"),
    ]
    if departments:
        params.append(("department", ",".join(departments)))
    data = await _get("/domain-search", "Domain Search", params)
    people = (_person(e) for e in data.get("emails") or [] if isinstance(e, dict))
    return [p for p in people if p is not None]


async def find_email(domain: str, first_name: str, last_name: str) -> Optional[str]:
    data = await _get(
        "/email-finder",
        "Email Finder",
        [("domain", domain), ("first_name", first_name), ("last_name", last_name)],
    )
    return verified_email(data.get("email"), data.get("score"), data.get("verification"))
