import asyncio

import pytest

from api.api_services import company_search
from services.hunt import apollo
from services.hunt import credits
from services.hunt.apollo import ApolloError
from services.hunt.filters import FilterGenerationError
from api.type_models.company_search import CompanySearchRequest
from tests.conftest import BLANK_FILTERS, make_filters, make_profile

pytestmark = pytest.mark.anyio

FILTERS = make_filters(hiring_locations=["dubai"], job_title_signals=["sales manager"])
USER = 1


def org(i: int) -> dict:
    return {"id": f"{i:024x}", "name": f"Co {i}"}


@pytest.fixture
def apollo_calls(monkeypatch):
    calls = []

    async def search_page(filters, page):
        calls.append(page)
        await asyncio.sleep(0.01)
        return [org(i) for i in range(100)], 100, 250

    monkeypatch.setattr(apollo, "search_page", search_page)
    return calls


@pytest.fixture
def llm_calls(monkeypatch):
    calls = []

    async def generate_filters(query, user_id, profile=None):
        calls.append((query, profile) if profile else query)
        return FILTERS

    monkeypatch.setattr(company_search, "generate_filters", generate_filters)
    return calls


def request(page: int = 1, filters=FILTERS, query: str = "sales in dubai") -> CompanySearchRequest:
    return CompanySearchRequest(query=query, page=page, filters=filters)


async def test_has_more_and_page_cap(apollo_calls, usage):
    first = await company_search.search(request(page=1), USER, None)
    third = await company_search.search(request(page=3), USER, None)
    eleventh = await company_search.search(request(page=11), USER, None)

    assert len(first.rows) == 100 and first.has_more and first.total_entries == 250
    assert not third.has_more
    assert eleventh.rows == [] and not eleventh.has_more
    assert apollo_calls == [1, 3]
    assert usage.used == 2 and first.credits_left == 49


async def test_repeat_page_is_served_from_cache_without_a_credit(apollo_calls, usage):
    await company_search.search(request(), USER, None)
    await company_search.search(request(), 2, None)

    assert apollo_calls == [1]
    assert usage.used == 1


async def test_each_page_saves_its_companies_once(apollo_calls, companies):
    await company_search.search(request(), USER, None)
    await company_search.search(request(), 2, None)

    assert companies.saves == [100]


async def test_a_failed_company_save_is_retried_on_the_next_search(apollo_calls, companies):
    companies.ok = False
    await company_search.search(request(), USER, None)
    companies.ok = True
    await company_search.search(request(), USER, None)
    await company_search.search(request(), USER, None)

    assert companies.saves == [100, 100]
    assert apollo_calls == [1]


async def test_shared_cache_serves_other_workers_without_a_credit(apollo_calls, usage, store):
    first = await company_search.search(request(), USER, None)
    company_search.clear_caches()
    again = await company_search.search(request(), 2, None)

    assert apollo_calls == [1]
    assert usage.used == 1
    assert len(store.data) == 1
    assert again.rows == first.rows and again.total_entries == first.total_entries


async def test_unreadable_shared_cache_entry_is_refetched(apollo_calls, store):
    await company_search.search(request(), USER, None)
    (key,) = store.data
    store.data[key] = {"rows": "not a list"}
    company_search.clear_caches()
    await company_search.search(request(), USER, None)

    assert apollo_calls == [1, 1]


async def test_concurrent_identical_searches_share_one_apollo_call(apollo_calls, usage):
    await asyncio.gather(*(company_search.search(request(), USER, None) for _ in range(3)))

    assert apollo_calls == [1]
    assert usage.used == 1


async def test_failed_apollo_call_refunds_the_credit_and_is_not_cached(monkeypatch, usage, store):
    calls = []

    async def search_page(filters, page):
        calls.append(page)
        raise ApolloError("down")

    monkeypatch.setattr(apollo, "search_page", search_page)
    for _ in range(2):
        with pytest.raises(ApolloError):
            await company_search.search(request(), USER, None)

    assert len(calls) == 2
    assert usage.used == 0 and usage.refunds == 2
    assert store.data == {}


async def test_an_empty_wallet_blocks_before_calling_apollo(apollo_calls, usage):
    usage.limit = 0

    with pytest.raises(credits.CreditLimitReached):
        await company_search.search(request(), USER, None)

    assert apollo_calls == []


async def test_same_query_calls_the_llm_once(apollo_calls, llm_calls):
    await company_search.search(request(filters=None, query="Sales in  Dubai"), USER, None)
    await company_search.search(request(filters=None, query="sales in dubai"), USER, None)

    assert llm_calls == ["Sales in  Dubai"]


async def test_new_searches_are_rate_limited_per_user(monkeypatch, apollo_calls, llm_calls):
    monkeypatch.setattr(company_search, "NEW_SEARCHES_PER_MINUTE", 2)
    await company_search.search(request(filters=None, query="one"), USER, None)
    await company_search.search(request(filters=None, query="two"), USER, None)
    await company_search.search(request(filters=None, query="one"), USER, None)

    with pytest.raises(company_search.TooManySearches):
        await company_search.search(request(filters=None, query="three"), USER, None)
    await company_search.search(request(filters=None, query="three"), 2, None)


async def test_jobs_are_searched_within_the_last_30_days_by_default(apollo_calls):
    result = await company_search.search(request(), USER, None)

    assert result.filters.job_posted_within_days == 30


async def test_an_asked_for_posting_window_is_kept(apollo_calls):
    filters = make_filters(hiring_locations=["dubai"], job_posted_within_days=7)

    result = await company_search.search(request(filters=filters), USER, None)

    assert result.filters.job_posted_within_days == 7


async def test_blank_query_and_empty_filters_are_rejected(apollo_calls):
    with pytest.raises(FilterGenerationError):
        await company_search.search(request(filters=None, query="   "), USER, None)
    with pytest.raises(FilterGenerationError):
        await company_search.search(request(filters=make_filters(**BLANK_FILTERS)), USER, None)

    assert apollo_calls == []


PROFILE = make_profile(current_title="Account Executive", seniority="senior", function="sales")


async def test_profile_fills_gaps_and_allows_a_blank_query(apollo_calls, llm_calls, profiles):
    profiles.data[USER] = PROFILE

    first = await company_search.search(request(filters=None, query=""), USER, None)
    more = await company_search.search(request(page=2, filters=first.filters, query=""), USER, None)
    typed = await company_search.search(request(filters=None, query="sales in dubai"), USER, None)

    assert first.used_profile and typed.used_profile and not more.used_profile
    assert llm_calls == [("", PROFILE), ("sales in dubai", PROFILE)]


async def test_profile_is_skipped_when_off_or_empty(apollo_calls, llm_calls, profiles):
    profiles.data[USER] = PROFILE
    off = await company_search.search(
        CompanySearchRequest(query="sales in dubai", use_profile=False), USER, None
    )
    profiles.data[2] = make_profile()
    empty = await company_search.search(request(filters=None), 2, None)

    assert not off.used_profile and not empty.used_profile
    assert llm_calls == ["sales in dubai"]
    with pytest.raises(FilterGenerationError):
        await company_search.search(request(filters=None, query=""), 2, None)


async def test_filters_cache_is_keyed_by_profile(apollo_calls, llm_calls, profiles):
    profiles.data[USER] = PROFILE
    await company_search.search(request(filters=None), USER, None)
    await company_search.search(request(filters=None), USER, None)
    profiles.data[USER] = make_profile(current_title="Sales Director", seniority="director")
    await company_search.search(request(filters=None), USER, None)
    await company_search.search(request(filters=None), 2, None)

    assert len(llm_calls) == 3


def test_rows_keep_only_safe_links():
    row = company_search.to_row(
        {
            "id": "a" * 24,
            "name": None,
            "primary_domain": "javascript:alert(1)",
            "website_url": "https://Example.com/about",
            "linkedin_url": "javascript:alert(1)",
            "logo_url": "http://cdn.example.com/logo.png",
            "founded_year": True,
        }
    )

    assert row.company_name == "Unknown"
    assert row.domain == "https://Example.com/about"
    assert row.linkedin_url is None
    assert row.linkedin_jobs_url is None
    assert row.logo_url == "http://cdn.example.com/logo.png"
    assert row.founded_year is None
    assert company_search.to_row({"id": "a" * 24, "primary_domain": " Acme.io "}).domain == "acme.io"


@pytest.mark.parametrize(
    "linkedin_url, jobs_url",
    [
        ("http://www.linkedin.com/company/acme", "https://www.linkedin.com/company/acme/jobs/"),
        ("https://linkedin.com/company/acme-labs/", "https://www.linkedin.com/company/acme-labs/jobs/"),
        ("www.linkedin.com/company/acme?trk=x", "https://www.linkedin.com/company/acme/jobs/"),
        ("https://uk.linkedin.com/company/acme/about", "https://www.linkedin.com/company/acme/jobs/"),
        ("https://www.linkedin.com/company/caf%C3%A9-co", "https://www.linkedin.com/company/caf%C3%A9-co/jobs/"),
        ("https://www.linkedin.com/in/someone", None),
        ("https://linkedin.com.evil.example/company/acme", None),
        ("javascript:alert(1)", None),
        (None, None),
    ],
)
def test_linkedin_jobs_link(linkedin_url, jobs_url):
    row = company_search.to_row({"id": "a" * 24, "linkedin_url": linkedin_url})

    assert row.linkedin_jobs_url == jobs_url


async def test_job_postings_come_from_the_shared_cache_without_a_credit(monkeypatch, usage):
    fetches = []

    async def get_job_postings(org_id):
        fetches.append(org_id)
        return [{"title": "Sales Manager"}]

    monkeypatch.setattr(apollo, "get_job_postings", get_job_postings)
    org_id = "c" * 24
    await company_search.job_postings(org_id, ["sales manager"], USER, None)
    company_search.clear_caches()
    result = await company_search.job_postings(org_id, ["sales manager"], 2, None)

    assert fetches == [org_id] and usage.used == 1
    assert result.postings[0].matches_role


async def test_malformed_cached_postings_are_skipped(usage, store):
    org_id = "d" * 24
    store.data[f"postings:{org_id}"] = [{"title": "Sales Manager"}, "junk", None]

    result = await company_search.job_postings(org_id, ["sales manager"], USER, None)

    assert [p.title for p in result.postings] == ["Sales Manager"]
    assert usage.used == 0


async def test_job_postings_match_roles_first_and_are_cached(monkeypatch, usage):
    fetches = []

    async def get_job_postings(org_id):
        fetches.append(org_id)
        return [
            {"title": "Software Engineer", "posted_at": "2026-10-30T00:00:00Z"},
            {
                "title": "Senior Sales Manager - MENA",
                "posted_at": "2026-09-01T00:00:00Z",
                "city": "Dubai",
                "country": "United Arab Emirates",
                "url": "https://jobs.example.com/1",
            },
            {"title": "Enterprise Account Executive", "posted_at": "2026-10-15T00:00:00Z"},
            {"title": "Sales Operations Analyst", "url": "javascript:alert(1)"},
            {"title": None},
        ]

    monkeypatch.setattr(apollo, "get_job_postings", get_job_postings)
    org_id = "b" * 24
    result = await company_search.job_postings(
        org_id, ["sales manager", "account executive", " "], USER, None
    )
    await company_search.job_postings(org_id, ["software engineer"], USER, None)

    titles = [p.title for p in result.postings]
    assert titles[:2] == ["Enterprise Account Executive", "Senior Sales Manager - MENA"]
    assert titles[-1] == "Untitled role"
    assert result.matched_count == 2 and result.total == 5
    assert result.postings[1].location == "Dubai, United Arab Emirates"
    assert all(p.url is None or p.url.startswith("https://") for p in result.postings)
    assert fetches == [org_id] and usage.used == 1
