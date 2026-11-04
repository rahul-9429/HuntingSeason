import httpx
import pytest

from services.hunt import apollo, contact_finder, reveal
from models.contact import Contact
from services import contact_llm, hunter
from services.hunter import HunterError
from tests.conftest import use_hunter_transport

pytestmark = pytest.mark.anyio

ORG = "a" * 24
USER = 1
DOMAIN = "acme.com"


def entry(email, first, last, position, confidence=90, status="valid", **fields):
    return {
        "value": email,
        "type": "personal",
        "confidence": confidence,
        "first_name": first,
        "last_name": last,
        "position": position,
        "verification": {"date": "2026-10-01", "status": status},
        **fields,
    }


def hunter_person(i, title, department=None, seniority=None, first=None, last=None):
    return {
        "email": f"person{i}@{DOMAIN}",
        "first_name": first or f"First{i}",
        "last_name": last or f"Last{i}",
        "title": title,
        "seniority": seniority,
        "department": department,
        "linkedin_url": None,
    }


@pytest.fixture
def hunter_on(monkeypatch):
    monkeypatch.setenv("HUNTER_API_KEY", "test-key")


async def test_domain_search_keeps_only_valid_confident_personal_emails(monkeypatch, hunter_on):
    seen = {}

    def handler(request):
        seen["request"] = request
        return httpx.Response(
            200,
            json={
                "data": {
                    "emails": [
                        entry("Priya@Acme.com", "Priya", "Sharma", "Engineering Manager",
                              linkedin="https://www.linkedin.com/in/priya", seniority="senior",
                              department="it"),
                        entry("low@acme.com", "Low", "Score", "CTO", confidence=40),
                        entry("maybe@acme.com", "Maybe", "Valid", "CTO", status="accept_all"),
                        {**entry("info@acme.com", "Info", None, "Office"), "type": "generic"},
                        entry("noname@acme.com", None, None, "Recruiter"),
                    ]
                }
            },
        )

    use_hunter_transport(monkeypatch, handler)
    people = await hunter.domain_search(DOMAIN, ["hr", "it"])

    request = seen["request"]
    assert request.headers["X-API-KEY"] == "test-key"
    assert "test-key" not in str(request.url)
    params = dict(request.url.params)
    assert params["domain"] == DOMAIN and params["type"] == "personal"
    assert params["department"] == "hr,it" and params["verification_status"] == "valid"
    assert people == [
        {
            "email": "priya@acme.com",
            "first_name": "Priya",
            "last_name": "Sharma",
            "title": "Engineering Manager",
            "seniority": "senior",
            "department": "it",
            "linkedin_url": "https://www.linkedin.com/in/priya",
        }
    ]


@pytest.mark.parametrize("status_code, expected", [(401, 502), (403, 429), (429, 429), (500, 502)])
async def test_hunter_errors_become_hunter_errors(monkeypatch, hunter_on, status_code, expected):
    use_hunter_transport(monkeypatch, lambda request: httpx.Response(status_code, json={"errors": []}))

    with pytest.raises(HunterError) as raised:
        await hunter.domain_search(DOMAIN, [])

    assert raised.value.status_code == expected


async def test_find_email_needs_a_valid_confident_result(monkeypatch, hunter_on):
    def respond(score, status):
        return lambda request: httpx.Response(
            200,
            json={"data": {"email": "Priya@acme.com", "score": score, "verification": {"status": status}}},
        )

    use_hunter_transport(monkeypatch, respond(80, "valid"))
    assert await hunter.find_email(DOMAIN, "Priya", "Sharma") == "priya@acme.com"
    use_hunter_transport(monkeypatch, respond(80, "accept_all"))
    assert await hunter.find_email(DOMAIN, "Priya", "Sharma") is None
    use_hunter_transport(monkeypatch, respond(30, "valid"))
    assert await hunter.find_email(DOMAIN, "Priya", "Sharma") is None


def test_bare_domain():
    assert hunter.bare_domain("https://www.acme.com/about") == "acme.com"
    assert hunter.bare_domain("acme.com") == "acme.com"
    assert hunter.bare_domain(None) is None


def test_departments_follow_the_roles():
    assert contact_finder.hunter_departments(["backend engineer", "account executive"]) == [
        "executive", "hr", "it", "management", "sales",
    ]
    assert contact_finder.hunter_departments([]) == ["executive", "hr", "management"]


def test_hunter_people_are_typed_by_title_department_and_seniority():
    titles = {
        "hiring_manager": ["engineering manager", "head of engineering"],
        "recruiter": contact_finder.RECRUITER_TITLES,
        "referrer": ["backend engineer"],
    }

    def kind(**fields):
        typed = contact_finder.type_by_title(hunter_person(1, **fields), titles)
        return typed and typed[0]

    assert kind(title="Engineering Manager") == "hiring_manager"
    assert kind(title="Recruiting Manager") == "recruiter"
    assert kind(title="People Partner", department="hr") == "recruiter"
    assert kind(title="Senior Backend Engineer") == "referrer"
    assert kind(title="Chief Executive Officer", seniority="executive") == "hiring_manager"
    assert kind(title="Office Coordinator", department="administrative") is None


def test_same_person_matches_apollos_obfuscated_last_name():
    apollo_person = {"first_name": "Priya", "last_name_obfuscated": "Sh***a"}

    assert contact_finder.same_person({"first_name": "priya", "last_name": "Sharma"}, apollo_person)
    assert not contact_finder.same_person({"first_name": "Priya", "last_name": "Singh"}, apollo_person)
    assert not contact_finder.same_person({"first_name": "Anita", "last_name": "Sharma"}, apollo_person)
    assert contact_finder.same_person(
        {"first_name": "Ashleigh", "last_name": "Zak"}, {"first_name": "Ashleigh", "last_name_obfuscated": "Zak"}
    )


@pytest.fixture
def sources(monkeypatch):
    apollo_results = {}
    hunter_results = {"people": [], "calls": 0, "error": None}

    async def search_people(org_id, titles, locations):
        return apollo_results.get(titles[0], [])

    async def hiring_manager_titles(roles, user_id):
        return ["engineering manager", "head of engineering"]

    async def domain_search(domain, departments):
        hunter_results["calls"] += 1
        if hunter_results["error"]:
            raise hunter_results["error"]
        return hunter_results["people"]

    monkeypatch.setattr(apollo, "search_people", search_people)
    monkeypatch.setattr(contact_llm, "hiring_manager_titles", hiring_manager_titles)
    monkeypatch.setattr(hunter, "domain_search", domain_search)
    return apollo_results, hunter_results


def apollo_person(i, title, first=None, obfuscated="Ab***z"):
    return {"id": f"p{i}", "first_name": first or f"First{i}", "last_name_obfuscated": obfuscated,
            "title": title, "has_email": True}


async def find(domain=DOMAIN, roles=("backend engineer",)):
    return await contact_finder.find_candidates(None, ORG, list(roles), [], USER, domain)


async def test_hunter_fills_the_slot_apollo_left_empty(sources, usage, store, hunter_on):
    apollo_results, hunter_results = sources
    apollo_results["engineering manager"] = [apollo_person(1, "Engineering Manager")]
    hunter_results["people"] = [
        hunter_person(2, "Senior Backend Engineer"),
        hunter_person(3, "Technical Recruiter", department="hr"),
    ]

    picked = await find()

    assert [(c.source, c.type) for c in picked] == [("apollo", "hiring_manager"), ("hunter", "recruiter")]
    assert usage.used == 1 and usage.refunds == 0


async def test_hunter_is_skipped_when_apollo_found_enough(sources, usage, store, hunter_on):
    apollo_results, hunter_results = sources
    apollo_results["engineering manager"] = [apollo_person(1, "Engineering Manager")]
    apollo_results["recruiter"] = [apollo_person(2, "Recruiter")]

    picked = await find()

    assert len(picked) == 2 and hunter_results["calls"] == 0 and usage.used == 0


async def test_hunter_results_are_shared_through_the_cache(sources, usage, store, hunter_on):
    _, hunter_results = sources
    hunter_results["people"] = [hunter_person(1, "Recruiter", department="hr")]

    await find()
    again = await find()

    assert hunter_results["calls"] == 1 and usage.used == 1
    assert [c.source for c in again] == ["hunter"]


async def test_hunter_needs_a_key_a_domain_and_a_credit(sources, usage, store, monkeypatch):
    _, hunter_results = sources
    hunter_results["people"] = [hunter_person(1, "Recruiter", department="hr")]

    assert await find() == []
    monkeypatch.setenv("HUNTER_API_KEY", "test-key")
    assert await find(domain=None) == []
    usage.limit = 0
    assert await find() == []
    assert hunter_results["calls"] == 0


async def test_a_hunter_failure_refunds_and_keeps_apollos_contacts(sources, usage, store, hunter_on):
    apollo_results, hunter_results = sources
    apollo_results["engineering manager"] = [apollo_person(1, "Engineering Manager")]
    hunter_results["error"] = HunterError("Hunter Domain Search limit reached", status_code=429)

    picked = await find()

    assert [c.source for c in picked] == ["apollo"]
    assert usage.used == 0 and usage.refunds == 1
    assert not any(key.startswith("hunter:") for key in store.data)


async def test_an_empty_hunter_search_is_refunded(sources, usage, store, hunter_on):
    await find()

    assert usage.used == 0 and usage.refunds == 1


async def test_hunter_skips_someone_apollo_already_picked(sources, usage, store, hunter_on):
    apollo_results, hunter_results = sources
    apollo_results["engineering manager"] = [
        apollo_person(1, "Engineering Manager", first="Priya", obfuscated="Sh***a")
    ]
    hunter_results["people"] = [
        hunter_person(2, "Engineering Manager", first="Priya", last="Sharma"),
        hunter_person(3, "Head of Engineering"),
    ]

    picked = await find()

    assert [(c.source, c.person.get("email")) for c in picked] == [
        ("apollo", None),
        ("hunter", f"person3@{DOMAIN}"),
    ]


async def test_hunter_is_refunded_when_none_of_its_people_are_used(sources, usage, store, hunter_on):
    apollo_results, hunter_results = sources
    apollo_results["engineering manager"] = [
        apollo_person(1, "Engineering Manager", first="Priya", obfuscated="Sh***a")
    ]
    hunter_results["people"] = [
        hunter_person(2, "Engineering Manager", first="Priya", last="Sharma"),
        hunter_person(3, "Office Coordinator", department="administrative"),
    ]

    picked = await find()

    assert [c.source for c in picked] == ["apollo"]
    assert usage.used == 0 and usage.refunds == 1


def revealed_contact(email=None, last_name="Sharma"):
    person = Contact(apollo_person_id="p1", company_id=1, first_name="Priya", last_name=last_name, email=email)
    person.id = 20
    return person


async def test_reveal_fills_a_missing_email_from_hunter(monkeypatch, hunter_on):
    calls = []

    async def find_email(domain, first_name, last_name):
        calls.append((domain, first_name, last_name))
        return "priya@acme.com"

    monkeypatch.setattr(hunter, "find_email", find_email)
    person = revealed_contact()
    await reveal.email_from_hunter(person, DOMAIN)

    assert calls == [(DOMAIN, "Priya", "Sharma")]
    assert person.email == "priya@acme.com" and person.email_source == "hunter" and person.has_email

    with_email = revealed_contact(email="priya@apollo.example")
    await reveal.email_from_hunter(with_email, DOMAIN)
    await reveal.email_from_hunter(revealed_contact(last_name=None), DOMAIN)
    assert len(calls) == 1


async def test_a_hunter_failure_during_reveal_is_ignored(monkeypatch, hunter_on):
    async def find_email(domain, first_name, last_name):
        raise HunterError("Couldn't reach Hunter Email Finder")

    monkeypatch.setattr(hunter, "find_email", find_email)
    person = revealed_contact()
    await reveal.email_from_hunter(person, DOMAIN)

    assert person.email is None
