import re
from functools import cache
from pathlib import Path
from typing import Optional

GENERIC_PREFIXES = frozenset(
    {
        "info", "sales", "support", "contact", "hello", "admin", "help", "team", "office",
        "noreply", "mail", "hr", "careers", "jobs", "marketing", "press", "media", "feedback",
        "enquiries", "inquiries", "general", "webmaster", "postmaster", "abuse", "security",
        "legal", "billing", "accounts", "service", "services", "orders", "newsletter",
        "helpdesk", "reception", "frontdesk", "privacy",
    }
)

_HONORIFICS = {"mr", "mrs", "ms", "miss", "dr", "prof", "sir", "eng", "sheikh"}
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "phd", "md", "mba"}
_GENERAL_CONTACT = re.compile(r"^general contact \d+$", re.IGNORECASE)
_IN_PARENTHESES = re.compile(r"^\(.*\)$")
_LOCAL_PART_SEPARATORS = re.compile(r"[._-]")
_TRAILING_DIGITS = re.compile(r"\d+$")


@cache
def _common_first_names() -> frozenset[str]:
    path = Path(__file__).parent / "data" / "common_first_names.txt"
    return frozenset(
        line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )


def _one_case(text: str) -> bool:
    return text.isupper() or text.islower()


def extract_name_from_email(email: str) -> Optional[str]:
    local = email.split("@", 1)[0].lower().split("+", 1)[0]
    tokens = [_TRAILING_DIGITS.sub("", token) for token in _LOCAL_PART_SEPARATORS.split(local)]
    tokens = [token for token in tokens if token]
    if not tokens:
        return None
    if _LOCAL_PART_SEPARATORS.sub("", local) in GENERIC_PREFIXES or tokens[0] in GENERIC_PREFIXES:
        return None
    first = tokens[0]
    if len(first) < 3 or not first.isalpha() or first not in _common_first_names():
        return None
    return " ".join(token.capitalize() for token in tokens[:2])


def _from_email(email: str) -> str:
    name = extract_name_from_email(email) if email else None
    return name.split()[0] if name else "there"


def _is_placeholder(name: str) -> bool:
    return bool(
        _GENERAL_CONTACT.match(name)
        or _IN_PARENTHESES.match(name)
        or (" " not in name and name.lower() in GENERIC_PREFIXES)
    )


def extract_first_name(name: Optional[str], email: str) -> str:
    name = (name or "").strip()
    if not name:
        return "there"
    if _is_placeholder(name):
        return _from_email(email)

    if "," in name:
        before, after = (part.strip() for part in name.split(",", 1))
        given = [word for word in after.split() if word.lower().strip(".") not in _SUFFIXES]
        name = " ".join(given) or before

    words = name.split()
    while words and words[0].lower().rstrip(".") in _HONORIFICS:
        words.pop(0)
    if not words:
        return _from_email(email)

    if words[0].lower() == "al" and len(words) > 1:
        full = " ".join(words)
        return full.title() if _one_case(full) else full

    first = words[0]
    if len(first.rstrip(".")) <= 1:
        return _from_email(email)
    return first.capitalize() if _one_case(first) else first
