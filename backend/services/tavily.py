import logging
import os
import re
from typing import Any, Optional
from urllib.parse import unquote, urlsplit

import httpx

from services.errors import ServiceError
from services.schemas.common import http_url, str_or_none

logger = logging.getLogger(__name__)

MAX_RESULTS = 10
MAX_CONTENT_CHARS = 800

_client = httpx.AsyncClient(base_url="https://api.tavily.com", timeout=30)
_LINKEDIN_PROFILE = re.compile(r"^/in/([^/?#]+)", re.IGNORECASE)


class TavilyError(ServiceError):
    status_code = 502


def configured() -> bool:
    return bool(os.getenv("TAVILY_API_KEY"))


def warn_if_unconfigured() -> None:
    if not configured():
        logger.warning(
            "TAVILY_API_KEY is not set; contact search skips the web search step",
            extra={"env_var": "TAVILY_API_KEY"},
        )


async def close_client() -> None:
    await _client.aclose()


def linkedin_profile(value: Any) -> Optional[str]:
    url = http_url(value)
    if url is None:
        return None
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    match = _LINKEDIN_PROFILE.match(parts.path)
    if not (host == "linkedin.com" or host.endswith(".linkedin.com")) or not match:
        return None
    return f"https://www.linkedin.com/in/{unquote(match[1]).lower()}"


async def search(query: str, include_domains: list[str]) -> list[dict[str, str]]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise TavilyError("TAVILY_API_KEY is not set", status_code=500)
    try:
        response = await _client.post(
            "/search",
            json={
                "query": query,
                "search_depth": "basic",
                "max_results": MAX_RESULTS,
                "include_domains": include_domains,
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
    except httpx.HTTPError as exc:
        raise TavilyError("Couldn't reach Tavily search") from exc

    if response.status_code == 401:
        raise TavilyError("Tavily rejected TAVILY_API_KEY")
    if response.status_code in (429, 432, 433):
        raise TavilyError("Tavily search limit reached", status_code=429)
    if response.is_error:
        logger.warning(
            "Tavily search returned %s: %s",
            response.status_code,
            response.text[:500],
            extra={"status_code": response.status_code},
        )
        raise TavilyError(f"Tavily search failed ({response.status_code})")

    try:
        results = response.json().get("results")
    except (ValueError, AttributeError) as exc:
        raise TavilyError("Tavily search returned an unreadable response") from exc

    found = []
    for result in results if isinstance(results, list) else []:
        if not isinstance(result, dict):
            continue
        url = http_url(result.get("url"))
        if url is None:
            continue
        found.append(
            {
                "url": url,
                "title": str_or_none(result.get("title")) or "",
                "content": (str_or_none(result.get("content")) or "")[:MAX_CONTENT_CHARS],
            }
        )
    return found
