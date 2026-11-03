from typing import Any, Optional
from urllib.parse import urlsplit

MAX_ITEMS = 10
MAX_TEXT_LENGTH = 100

# Apollo can't filter for remote jobs, so these never make it into a location filter
NOT_A_LOCATION = {"remote", "anywhere", "worldwide", "global"}


def is_place(value: str) -> bool:
    return value.lower() not in NOT_A_LOCATION


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    found = []
    for value in values:
        if value.lower() not in seen:
            seen.add(value.lower())
            found.append(value)
    return found[:MAX_ITEMS]


def clean_texts(values: list[str]) -> list[str]:
    cleaned = (" ".join(v.split()) for v in values)
    return unique([v for v in cleaned if v and len(v) <= MAX_TEXT_LENGTH])


def str_or_none(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def http_url(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    parts = urlsplit(value.strip())
    return value.strip() if parts.scheme in ("http", "https") and parts.netloc else None
