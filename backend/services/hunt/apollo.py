import asyncio
import logging
import os
from datetime import date, timedelta
from typing import Any, Optional

import httpx

from services.errors import ServiceError
from services.schemas.company import CompanyFilters

logger = logging.getLogger(__name__)

PER_PAGE = 100
JOB_POSTINGS_PER_PAGE = 1000
PEOPLE_PER_PAGE = 25
MAX_MATCHES_PER_CALL = 10
RETRY_DELAYS = (0.5, 1.5)
MAX_RETRY_AFTER_SECONDS = 5

_client = httpx.AsyncClient(
    base_url="https://api.apollo.io/api/v1",
    timeout=30,
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
)


class ApolloError(ServiceError):
    status_code = 502


async def close_client() -> None:
    await _client.aclose()


def build_params(filters: CompanyFilters, page: int) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = [("page", str(page)), ("per_page", str(PER_PAGE))]

    def add_list(key: str, values: list[str]) -> None:
        params.extend((f"{key}[]", v) for v in values)

    # organization_locations is where the company is headquartered; where it's
    # hiring is organization_job_locations
    add_list("organization_locations", filters.company_locations)
    add_list("organization_num_employees_ranges", filters.employee_ranges)
    add_list("q_organization_keyword_tags", filters.keyword_tags)
    add_list("market_segments", list(filters.market_segments))
    add_list("q_organization_job_titles", filters.job_title_signals)
    add_list("organization_job_locations", filters.hiring_locations)

    min_jobs = max(1, filters.min_active_job_postings or 0)
    params.append(("organization_num_jobs_range[min]", str(min_jobs)))
    if filters.job_posted_within_days is not None:
        since = date.today() - timedelta(days=filters.job_posted_within_days)
        params.append(("organization_job_posted_at_range[min]", since.isoformat()))

    if filters.founded_year_min is not None:
        params.append(("organization_founded_year_range[min]", str(filters.founded_year_min)))
    if filters.founded_year_max is not None:
        params.append(("organization_founded_year_range[max]", str(filters.founded_year_max)))
    return params


def _headers() -> dict[str, str]:
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        raise ApolloError("APOLLO_API_KEY is not set", status_code=500)
    return {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }


def _retry_after(response: httpx.Response) -> Optional[float]:
    try:
        seconds = float(response.headers.get("retry-after", ""))
    except ValueError:
        return None
    return seconds if 0 <= seconds <= MAX_RETRY_AFTER_SECONDS else None


async def _send(
    method: str,
    path: str,
    endpoint_name: str,
    params: list[tuple[str, str]],
    json_body: Optional[dict[str, Any]] = None,
) -> httpx.Response:
    headers = _headers()
    for delay in (*RETRY_DELAYS, None):
        try:
            # A tuple, not the list: httpx types params as an invariant list of (str, PrimitiveData)
            response = await _client.request(
                method, path, params=tuple(params), json=json_body, headers=headers
            )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            if delay is None:
                raise ApolloError(f"Couldn't reach Apollo {endpoint_name}") from exc
            logger.warning(
                "Apollo %s unreachable, retrying in %ss",
                endpoint_name,
                delay,
                extra={"apollo_endpoint": endpoint_name, "retry_in_s": delay},
            )
            await asyncio.sleep(delay)
            continue
        except httpx.TimeoutException as exc:
            raise ApolloError(f"Apollo {endpoint_name} timed out, try again") from exc
        except httpx.HTTPError as exc:
            raise ApolloError(f"Couldn't reach Apollo {endpoint_name}") from exc

        wait = _retry_after(response) if response.status_code == 429 else None
        if wait is not None and delay is not None:
            logger.warning(
                "Apollo %s rate limited, retrying in %ss",
                endpoint_name,
                wait,
                extra={"apollo_endpoint": endpoint_name, "retry_in_s": wait},
            )
            await asyncio.sleep(wait)
            continue
        return response
    raise AssertionError("unreachable")


async def _request(
    method: str,
    path: str,
    endpoint_name: str,
    params: list[tuple[str, str]],
    json_body: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    response = await _send(method, path, endpoint_name, params, json_body)

    if response.status_code == 401:
        raise ApolloError("Apollo rejected APOLLO_API_KEY")
    if response.status_code == 403:
        raise ApolloError(
            f"This Apollo API key has no access to the {endpoint_name} endpoint"
        )
    if response.status_code == 429:
        raise ApolloError("Apollo rate limit reached, try again in a minute", status_code=429)
    if response.is_error:
        logger.warning(
            "Apollo %s returned %s: %s",
            endpoint_name,
            response.status_code,
            response.text[:500],
            extra={"apollo_endpoint": endpoint_name, "status_code": response.status_code},
        )
        raise ApolloError(f"Apollo {endpoint_name} failed ({response.status_code})")

    try:
        return response.json()
    except ValueError as exc:
        raise ApolloError(f"Apollo {endpoint_name} returned an unreadable response") from exc


async def search_page(
    filters: CompanyFilters, page: int
) -> tuple[list[dict[str, Any]], int, Optional[int]]:
    body = await _request(
        "POST", "/mixed_companies/search", "Organization Search", build_params(filters, page)
    )

    organizations: list[dict[str, Any]] = body.get("organizations") or []
    accounts: list[dict[str, Any]] = body.get("accounts") or []

    companies: list[dict[str, Any]] = []
    seen: set[str] = set()
    for org in organizations + [
        {**a, "id": a.get("organization_id") or a.get("id")} for a in accounts
    ]:
        org_id = org.get("id")
        if not org_id or org_id in seen:
            continue
        seen.add(org_id)
        companies.append(org)

    total = (body.get("pagination") or {}).get("total_entries")
    return companies, len(organizations) + len(accounts), total if isinstance(total, int) else None


async def get_job_postings(org_id: str) -> list[dict[str, Any]]:
    body = await _request(
        "GET",
        f"/organizations/{org_id}/job_postings",
        "Job Postings",
        [("page", "1"), ("per_page", str(JOB_POSTINGS_PER_PAGE))],
    )
    return body.get("organization_job_postings") or []


async def search_people(
    org_id: str, titles: list[str], locations: list[str]
) -> list[dict[str, Any]]:
    params = [
        ("organization_ids[]", org_id),
        ("page", "1"),
        ("per_page", str(PEOPLE_PER_PAGE)),
        *(("person_titles[]", t) for t in titles),
        *(("person_locations[]", loc) for loc in locations),
    ]
    body = await _request("POST", "/mixed_people/api_search", "People Search", params)
    return [p for p in body.get("people") or [] if isinstance(p, dict)]


async def match_people(person_ids: list[str]) -> list[dict[str, Any]]:
    body = await _request(
        "POST",
        "/people/bulk_match",
        "People Enrichment",
        [],
        {
            "details": [{"id": i} for i in person_ids[:MAX_MATCHES_PER_CALL]],
            "reveal_personal_emails": False,
        },
    )
    return [m for m in body.get("matches") or [] if isinstance(m, dict)]
