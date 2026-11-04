import json

import httpx
import pytest

from services.hunt import apollo, contact_finder
from services import contact_llm, hunter, tavily
from services.contact_llm import ContactLLMError
from services.schemas.contacts import WebPerson
from services.tavily import TavilyError
from tests.conftest import use_tavily_transport

pytestmark = pytest.mark.anyio

ORG = "a" * 24
USER = 1
DOMAIN = "acme.com"
COMPANY = "Acme"


def result(slug, name, title):
    return {
        "url": f"https://www.linkedin.com/in/{slug}",
        "title": f"{name} - {title} - {COMPANY} | LinkedIn",
        "content": f"{name} is {title} at {COMPANY}.",
    }


@pytest.fixture
def tavily_on(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")


async def test_search_sends_a_bearer_key_and_keeps_http_results(monkeypatch, tavily_on):
    seen = {}

    def handler(request):
        seen["request"] = request
        return httpx.Response(
            200,
            json={
                "results": [
                    {"url": "https://www.linkedin.com/in/priya", "title": "Priya", "content": "x" * 2000},
                    {"url": "javascript:alert(1)", "title": "Bad", "content": ""},
                    "junk",
                ]
            },
        )

    use_tavily_transport(monkeypatch, handler)
    results = await tavily.search('"Acme" "recruiter"', ["linkedin.com"])

    request = seen["request"]
    body = json.loads(request.content)
    assert request.headers["Authorization"] == "Bearer tvly-test"
    assert body["query"] == '"Acme" "recruiter"' and body["include_domains"] == ["linkedin.com"]
    assert body["search_depth"] == "basic" and "api_key" not in body
    assert [r["url"] for r in results] == ["https://www.linkedin.com/in/priya"]
    assert len(results[0]["content"]) == tavily.MAX_CONTENT_CHARS


@pytest.mark.parametrize("status_code, expected", [(401, 502), (429, 429), (432, 429), (433, 429), (500, 502)])
async def test_tavily_errors_become_tavily_errors(monkeypatch, tavily_on, status_code, expected):
    use_tavily_transport(monkeypatch, lambda request: httpx.Response(status_code, json={}))

    with pytest.raises(TavilyError) as raised:
        await tavily.search("x", [])

    assert raised.value.status_code == expected


def test_linkedin_profile_urls_are_normalized():
    assert (
        tavily.linkedin_profile("https://uk.linkedin.com/in/Priya-Sharma-123?trk=abc")
        == "https://www.linkedin.com/in/priya-sharma-123"
    )
    assert tavily.linkedin_profile("https://www.linkedin.com/company/acme") is None
    assert tavily.linkedin_profile("https://linkedin.com.evil.example/in/priya") is None
    assert tavily.linkedin_profile("not a url") is None


def test_only_people_the_results_back_up_are_kept():
    results = [result("priya-sharma", "Priya Sharma", "Engineering Manager"), result("tom", "Tom Lee", "Recruiter")]
    found = [
        WebPerson(name="Priya Sharma", title="Engineering Manager", url="https://www.linkedin.com/in/priya-sharma"),
        WebPerson(name="Priya Sharma", title="Engineering Manager", url="https://www.linkedin.com/in/priya-sharma"),
        WebPerson(name="Made Up", title="CTO", url="https://www.linkedin.com/in/made-up"),
        WebPerson(name="Anita Rao", title="Recruiter", url="https://www.linkedin.com/in/tom"),
        WebPerson(name="Tom", title="Recruiter", url="https://www.linkedin.com/in/tom"),
        WebPerson(name="Tom Lee", title="", url="https://www.linkedin.com/in/tom"),
    ]

    people = contact_finder.verified_web_people(found, results)

    assert people == [
        {
            "first_name": "Priya",
            "last_name": "Sharma",
            "title": "Engineering Manager",
            "linkedin_url": "https://www.linkedin.com/in/priya-sharma",
            "email": None,
        }
    ]


def test_web_search_asks_for_the_missing_types_first():
    titles = {
        "hiring_manager": ["engineering manager", "head of engineering"],
        "recruiter": ["recruiter", "technical recruiter", "talent acquisition"],
        "referrer": ["backend engineer"],
    }
    picked = [contact_finder.Candidate({"id": "p1"}, "hiring_manager", 90)]

    assert contact_finder._web_titles(titles, picked) == [
        "recruiter", "backend engineer", "technical recruiter", "talent acquisition",
    ]


@pytest.fixture
def sources(monkeypatch):
    state = {
        "apollo": {},
        "hunter": [],
        "results": [],
        "people": [],
        "web_error": None,
        "tavily_calls": 0,
        "hunter_calls": 0,
        "emails": {},
    }

    async def search_people(org_id, titles, locations):
        return state["apollo"].get(titles[0], [])

    async def hiring_manager_titles(roles, user_id):
        return ["engineering manager", "head of engineering"]

    async def domain_search(domain, departments):
        state["hunter_calls"] += 1
        return state["hunter"]

    async def find_email(domain, first_name, last_name):
        return state["emails"].get(first_name)

    async def search(query, include_domains):
        state["tavily_calls"] += 1
        state["query"] = query
        if isinstance(state["web_error"], TavilyError):
            raise state["web_error"]
        return state["results"]

    async def web_people(company, domain, titles, results, user_id):
        if isinstance(state["web_error"], ContactLLMError):
            raise state["web_error"]
        return state["people"]

    monkeypatch.setattr(apollo, "search_people", search_people)
    monkeypatch.setattr(contact_llm, "hiring_manager_titles", hiring_manager_titles)
    monkeypatch.setattr(hunter, "domain_search", domain_search)
    monkeypatch.setattr(hunter, "find_email", find_email)
    monkeypatch.setattr(tavily, "search", search)
    monkeypatch.setattr(contact_llm, "web_people", web_people)
    return state


def apollo_person(i, title):
    return {"id": f"p{i}", "first_name": f"First{i}", "last_name_obfuscated": "Ab***z",
            "title": title, "has_email": True}


def web(slug, name, title):
    return result(slug, name, title), WebPerson(name=name, title=title, url=f"https://www.linkedin.com/in/{slug}")


def with_web(state, *people):
    state["results"] = [r for r, _ in people]
    state["people"] = [p for _, p in people]


async def find(locations=()):
    return await contact_finder.find_candidates(
        None, ORG, ["backend engineer"], list(locations), USER, DOMAIN, COMPANY
    )


async def test_tavily_fills_what_apollo_and_hunter_left_empty(sources, usage, store, tavily_on):
    sources["apollo"]["engineering manager"] = [apollo_person(1, "Engineering Manager")]
    with_web(sources, web("tom-lee", "Tom Lee", "Technical Recruiter"))

    picked = await find(locations=["dubai"])

    assert [(c.source, c.type) for c in picked] == [("apollo", "hiring_manager"), ("tavily", "recruiter")]
    assert picked[1].person["linkedin_url"] == "https://www.linkedin.com/in/tom-lee"
    assert picked[1].person["email"] is None
    assert '"Acme"' in sources["query"] and '"recruiter"' in sources["query"] and "dubai" in sources["query"]
    assert usage.used == 1


async def test_hunter_runs_before_tavily(sources, usage, store, tavily_on, monkeypatch):
    monkeypatch.setenv("HUNTER_API_KEY", "test-key")
    sources["hunter"] = [
        {"email": "a@acme.com", "first_name": "Ann", "last_name": "Lee", "title": "Engineering Manager",
         "seniority": None, "department": None, "linkedin_url": None},
        {"email": "b@acme.com", "first_name": "Bob", "last_name": "Ray", "title": "Recruiter",
         "seniority": None, "department": "hr", "linkedin_url": None},
    ]

    picked = await find()

    assert [c.source for c in picked] == ["hunter", "hunter"]
    assert sources["tavily_calls"] == 0 and usage.used == 1


async def test_web_contacts_get_an_email_only_from_hunter(sources, usage, store, tavily_on, monkeypatch):
    with_web(sources, web("tom-lee", "Tom Lee", "Recruiter"))
    sources["emails"] = {"Tom": "tom@acme.com"}

    without_hunter = await find()
    assert without_hunter[0].person["email"] is None

    monkeypatch.setenv("HUNTER_API_KEY", "test-key")
    with_hunter = await find()
    assert with_hunter[0].person["email"] == "tom@acme.com"


async def test_web_results_are_shared_through_the_cache(sources, usage, store, tavily_on):
    with_web(sources, web("tom-lee", "Tom Lee", "Recruiter"))

    await find()
    await find()

    assert sources["tavily_calls"] == 1 and usage.used == 1


@pytest.mark.parametrize(
    "error", [TavilyError("Tavily search limit reached", status_code=429), ContactLLMError("down")]
)
async def test_a_failed_web_search_is_refunded_and_not_cached(sources, usage, store, tavily_on, error):
    sources["apollo"]["engineering manager"] = [apollo_person(1, "Engineering Manager")]
    with_web(sources, web("tom-lee", "Tom Lee", "Recruiter"))
    sources["web_error"] = error

    picked = await find()

    assert [c.source for c in picked] == ["apollo"]
    assert usage.used == 0 and usage.refunds == 1
    assert not any(key.startswith("tavily:") for key in store.data)


async def test_a_web_search_that_finds_nobody_is_refunded(sources, usage, store, tavily_on):
    sources["results"] = [result("someone", "Some One", "Office Coordinator")]

    assert await find() == []
    assert usage.used == 0 and usage.refunds == 1


async def test_a_web_search_whose_people_all_go_unused_is_refunded(sources, usage, store, tavily_on):
    with_web(sources, web("some-one", "Some One", "Office Coordinator"))

    assert await find() == []
    assert usage.used == 0 and usage.refunds == 1


async def test_tavily_needs_a_key_and_a_credit(sources, usage, store, monkeypatch):
    with_web(sources, web("tom-lee", "Tom Lee", "Recruiter"))

    assert await find() == []
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    usage.limit = 0
    assert await find() == []
    assert sources["tavily_calls"] == 0
