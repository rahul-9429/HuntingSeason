from datetime import date, timedelta

import httpx
import pytest

from services.hunt import apollo
from services.hunt.apollo import ApolloError
from tests.conftest import make_filters, use_apollo_transport

pytestmark = pytest.mark.anyio

WORKED_EXAMPLE = make_filters(
    hiring_locations=["united arab emirates"],
    employee_ranges=["10,200"],
    market_segments=["saas"],
    job_title_signals=["sales manager", "account executive", "business development manager"],
    founded_year_min=2020,
)


def test_build_params_matches_the_worked_example():
    assert apollo.build_params(WORKED_EXAMPLE, 1) == [
        ("page", "1"),
        ("per_page", "100"),
        ("organization_num_employees_ranges[]", "10,200"),
        ("market_segments[]", "saas"),
        ("q_organization_job_titles[]", "sales manager"),
        ("q_organization_job_titles[]", "account executive"),
        ("q_organization_job_titles[]", "business development manager"),
        ("organization_job_locations[]", "united arab emirates"),
        ("organization_num_jobs_range[min]", "1"),
        ("organization_founded_year_range[min]", "2020"),
    ]


def test_hiring_and_headquarters_locations_are_separate_filters():
    params = apollo.build_params(make_filters(hiring_locations=["dubai"], company_locations=["india"]), 1)

    assert ("organization_job_locations[]", "dubai") in params
    assert ("organization_locations[]", "india") in params
    assert ("organization_job_locations[]", "india") not in params


def test_remote_is_not_a_location():
    filters = make_filters(hiring_locations=["Remote", "india"], company_locations=["anywhere"])

    assert filters.hiring_locations == ["india"] and filters.company_locations == []


def test_hiring_filters_map_to_params():
    params = apollo.build_params(
        make_filters(keyword_tags=["logistics"], min_active_job_postings=5, job_posted_within_days=7),
        2,
    )

    assert ("organization_num_jobs_range[min]", "5") in params
    since = (date.today() - timedelta(days=7)).isoformat()
    assert ("organization_job_posted_at_range[min]", since) in params


async def test_search_page_merges_accounts_and_reads_total(monkeypatch):
    org = lambda i: {"id": f"{i:024x}", "name": f"Co {i}"}
    seen = {}

    def handler(request):
        seen["request"] = request
        return httpx.Response(
            200,
            json={
                "organizations": [org(1), org(2)],
                "accounts": [
                    {"id": "acct-1", "organization_id": org(2)["id"]},
                    {"id": "acct-2", "organization_id": org(3)["id"]},
                ],
                "pagination": {"total_entries": 4},
            },
        )

    use_apollo_transport(monkeypatch, handler)
    companies, page_size, total = await apollo.search_page(WORKED_EXAMPLE, 1)

    assert [c["id"] for c in companies] == [org(1)["id"], org(2)["id"], org(3)["id"]]
    assert (page_size, total) == (4, 4)
    request = seen["request"]
    assert request.method == "POST" and request.content == b""
    assert request.headers["x-api-key"] == "test"
    assert request.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize(
    "response, status, detail",
    [
        (httpx.Response(401), 502, "rejected"),
        (httpx.Response(403), 502, "no access to the Organization Search endpoint"),
        (httpx.Response(429), 429, "rate limit"),
        (httpx.Response(500), 502, "failed (500)"),
        (httpx.Response(200, text="<html>"), 502, "unreadable"),
    ],
)
async def test_apollo_errors_become_readable_messages(monkeypatch, response, status, detail):
    use_apollo_transport(monkeypatch, lambda request: response)

    with pytest.raises(ApolloError) as error:
        await apollo.search_page(WORKED_EXAMPLE, 1)

    assert error.value.status_code == status
    assert detail in error.value.detail


async def test_missing_api_key_is_a_clear_server_error(monkeypatch):
    monkeypatch.delenv("APOLLO_API_KEY")

    with pytest.raises(ApolloError) as error:
        await apollo.search_page(WORKED_EXAMPLE, 1)

    assert error.value.status_code == 500
    assert "APOLLO_API_KEY" in error.value.detail


async def test_connection_failures_are_retried(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={"organizations": []})

    use_apollo_transport(monkeypatch, handler)
    await apollo.search_page(WORKED_EXAMPLE, 1)

    assert len(calls) == 3


async def test_short_rate_limit_waits_are_retried_once(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(200, json={"organizations": []})

    use_apollo_transport(monkeypatch, handler)
    await apollo.search_page(WORKED_EXAMPLE, 1)

    assert len(calls) == 2


async def test_read_timeouts_are_not_retried(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("slow", request=request)

    use_apollo_transport(monkeypatch, handler)
    with pytest.raises(ApolloError):
        await apollo.search_page(WORKED_EXAMPLE, 1)

    assert len(calls) == 1
