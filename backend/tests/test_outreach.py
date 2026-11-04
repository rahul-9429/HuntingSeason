import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from api.api_services import contacts, outreach
from services.hunt import apollo, contact_finder, reveal
from services.hunt import credits
from services.hunt.apollo import ApolloError
from api.dependencies.authenticate import get_current_user_claims
from api.main import app
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db
from models.company import Company
from models.contact import Contact
from models.user_company import UserCompany
from models.user_contact import UserContact
from services import contact_llm
from services.contact_llm import ContactLLMError
from tests.conftest import use_apollo_transport

pytestmark = pytest.mark.anyio

ORG = "a" * 24
USER = 1


def person(i, title, has_email=True):
    return {
        "id": f"p{i}",
        "first_name": f"First{i}",
        "last_name_obfuscated": "Ab***z",
        "title": title,
        "has_email": has_email,
    }


@pytest.fixture
def people(monkeypatch):
    results = {}
    calls = []

    async def search_people(org_id, titles, locations):
        calls.append((titles[0], bool(locations)))
        return results.get((titles[0], bool(locations)), [])

    async def hiring_manager_titles(roles, user_id):
        return ["engineering manager", "head of engineering"]

    monkeypatch.setattr(apollo, "search_people", search_people)
    monkeypatch.setattr(contact_llm, "hiring_manager_titles", hiring_manager_titles)
    return results, calls


async def test_search_people_filters_by_org_titles_and_locations(monkeypatch):
    seen = {}

    def handler(request):
        seen["request"] = request
        return httpx.Response(
            200, json={"people": [person(1, "Recruiter"), None], "total_entries": 1}
        )

    use_apollo_transport(monkeypatch, handler)
    found = await apollo.search_people(
        ORG, ["recruiter", "talent acquisition"], ["dubai"]
    )

    params = list(seen["request"].url.params.multi_items())
    assert seen["request"].url.path.endswith("/mixed_people/api_search")
    assert ("organization_ids[]", ORG) in params
    assert [v for k, v in params if k == "person_titles[]"] == [
        "recruiter",
        "talent acquisition",
    ]
    assert ("person_locations[]", "dubai") in params
    assert [p["id"] for p in found] == ["p1"]


async def test_match_people_sends_ids_in_the_body(monkeypatch):
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"matches": [{"id": "p1"}, None], "credits_consumed": 1}
        )

    use_apollo_transport(monkeypatch, handler)
    matches = await apollo.match_people([f"p{i}" for i in range(12)])

    assert len(seen["body"]["details"]) == apollo.MAX_MATCHES_PER_CALL
    assert seen["body"]["reveal_personal_emails"] is False
    assert matches == [{"id": "p1"}]


async def test_two_contacts_at_most_the_best_hiring_manager_then_recruiter(
    people, store
):
    results, calls = people
    results[("engineering manager", True)] = [
        person(1, "Engineering Manager", has_email=False),
        person(2, "Head of Engineering"),
    ]
    results[("recruiter", True)] = [person(3, "Recruiter")]
    results[("backend engineer", True)] = [person(4, "Backend Engineer")]

    picked = await contact_finder.find_candidates(
        None, ORG, ["backend engineer"], ["dubai"], USER
    )

    assert [(c.type, c.person["id"]) for c in picked] == [
        ("hiring_manager", "p2"),
        ("recruiter", "p3"),
    ]
    assert calls == [("engineering manager", True), ("recruiter", True)]


async def test_a_type_missing_in_the_location_is_searched_without_it(people, store):
    results, calls = people
    results[("engineering manager", True)] = [person(1, "Engineering Manager")]
    results[("recruiter", False)] = [person(2, "Recruiter")]

    picked = await contact_finder.find_candidates(
        None, ORG, ["backend engineer"], ["dubai"], USER
    )

    assert [c.person["id"] for c in picked] == ["p1", "p2"]
    assert ("recruiter", False) in calls and ("engineering manager", False) not in calls
    assert picked[0].relevance > picked[1].relevance


async def test_the_next_best_fill_in_when_a_type_has_nobody(people, store):
    results, _ = people
    results[("engineering manager", False)] = [
        person(1, "Engineering Manager"),
        person(2, "Office Manager"),
        person(3, "Head of Engineering"),
    ]

    picked = await contact_finder.find_candidates(
        None, ORG, ["backend engineer"], [], USER
    )

    assert [(c.type, c.person["id"]) for c in picked] == [
        ("hiring_manager", "p1"),
        ("hiring_manager", "p3"),
    ]


async def test_a_person_is_kept_under_one_type_only(people, store):
    results, _ = people
    results[("engineering manager", False)] = [person(1, "Engineering Manager")]
    results[("backend engineer", False)] = [
        person(1, "Engineering Manager"),
        person(2, "Backend Engineer"),
    ]

    picked = await contact_finder.find_candidates(
        None, ORG, ["backend engineer"], [], USER
    )

    assert [(c.type, c.person["id"]) for c in picked] == [
        ("hiring_manager", "p1"),
        ("referrer", "p2"),
    ]


async def test_people_searches_come_from_the_shared_cache(people, store):
    results, calls = people
    results[("recruiter", False)] = [person(1, "Recruiter"), person(2, "Recruiter")]

    await contact_finder.find_candidates(None, ORG, [], [], USER)
    await contact_finder.find_candidates(None, ORG, [], [], 2)

    assert calls.count(("recruiter", False)) == 1
    assert any(key.startswith("people:") for key in store.data)


async def test_no_roles_means_leadership_and_recruiters_only(people, store):
    results, calls = people

    await contact_finder.find_candidates(None, ORG, [], [], USER)

    assert [title for title, _ in calls] == ["founder", "recruiter"]


async def test_a_failed_titles_call_falls_back_to_leadership(
    people, store, monkeypatch
):
    _, calls = people

    async def failing(roles, user_id):
        raise ContactLLMError("down")

    monkeypatch.setattr(contact_llm, "hiring_manager_titles", failing)
    await contact_finder.find_candidates(None, ORG, ["backend engineer"], [], USER)

    assert [title for title, _ in calls] == ["founder", "recruiter", "backend engineer"]


def test_relevance_rewards_title_match_email_and_location():
    titles = ["engineering manager"]

    assert contact_finder.relevance("Engineering Manager", titles, True, True) == 100
    assert contact_finder.relevance("Engineering Manager", titles, False, False) == 70
    assert contact_finder.relevance("Office Manager", titles, False, False) == 50
    assert contact_finder.relevance(None, titles, False, False) == 30


def test_relevance_demotes_titles_that_only_match_on_paper():
    titles = ["engineering manager"]
    real = contact_finder.relevance("Engineering Manager", titles, True, True)

    # Same words, but none of these people can hire you.
    for title in (
        "Former Engineering Manager",
        "Engineering Manager (Retired)",
        "Engineering Manager Intern",
        "Assistant to the Engineering Manager",
    ):
        assert contact_finder.relevance(title, titles, True, True) < real

    # A weaker title with nothing against it still beats a disqualified match.
    assert contact_finder.relevance("Office Manager", titles, True, True) > contact_finder.relevance(
        "Former Engineering Manager", titles, True, True
    )


def test_demotion_matches_whole_words_only():
    # "intern" inside "internal", "ex" inside "experience": not demotions.
    assert contact_finder.demotion("Senior Internal Auditor") == 0
    assert contact_finder.demotion("Head of Experience Design") == 0
    assert contact_finder.demotion(None) == 0

    assert contact_finder.demotion("Marketing Intern") == 25
    assert contact_finder.demotion("Former CTO") == 30


def test_demotion_is_capped_so_a_title_is_never_buried():
    piled_on = contact_finder.demotion("Former Retired Student Intern Volunteer")

    assert piled_on == contact_finder.MAX_DEMOTION
    assert contact_finder.relevance("Former Retired Student Intern", ["intern"], True, True) >= 0


def make_row(revealed=False, has_email=True, domain="https://www.acme.com/about"):
    company = Company(apollo_org_id=ORG, name="Acme", domain=domain)
    company.id = 10
    person_row = Contact(
        apollo_person_id="p1",
        company_id=10,
        first_name="Priya",
        last_name="Sharma" if revealed else None,
        last_name_obfuscated="Sh***a",
        title="Engineering Manager",
        has_email=has_email,
        email="priya@acme.com" if revealed else None,
        city="Dubai",
        country="United Arab Emirates",
        revealed_at=datetime.now(timezone.utc) if revealed else None,
    )
    person_row.id = 20
    link = UserContact(
        user_id=USER,
        contact_id=20,
        user_company_id=30,
        type="hiring_manager",
        relevance=85,
    )
    link.id = 40
    link.found_at = datetime.now(timezone.utc)
    return link, person_row, company, ["backend engineer"]


def test_an_unrevealed_contact_shows_a_masked_email_and_partial_name():
    out = contacts.to_contact_out(*make_row()).model_dump(by_alias=True)

    assert out["name"] == "Priya Sh***a"
    assert out["email"] is None and out["emailMasked"] == "••••@acme.com"
    assert out["revealed"] is False
    assert out["source"] == "apollo" and out["emailSource"] is None
    assert out["location"] == "Dubai, United Arab Emirates"
    assert out["company"]["domain"] == "acme.com"
    assert out["signals"][0]["label"] == "Acme is hiring for backend engineer"


def test_a_revealed_contact_shows_the_full_name_and_email():
    out = contacts.to_contact_out(*make_row(revealed=True)).model_dump(by_alias=True)

    assert out["name"] == "Priya Sharma"
    assert out["email"] == "priya@acme.com" and out["emailMasked"] is None


def test_a_stuck_search_reads_as_failed():
    target = UserCompany(
        user_id=USER, company_id=10, roles=[], locations=[], status="searching"
    )
    target.contacts_found = 0
    target.searched_at = (
        datetime.now(timezone.utc) - outreach.STUCK_AFTER - timedelta(seconds=1)
    )

    assert outreach.to_outreach_company(target, ORG).status == "failed"
    target.searched_at = datetime.now(timezone.utc)
    assert outreach.to_outreach_company(target, ORG).status == "searching"


class FakeSession:
    def __init__(self, row):
        self.row = row

    async def execute(self, statement):
        row = self.row

        class Result:
            def tuples(self):
                return self

            def first(self):
                return row

        return Result()

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def refresh(self, obj):
        pass


@pytest.fixture
def reveal_person(monkeypatch):
    calls = []

    def stub(outcome):
        async def _reveal_person(db, contact_id, domain):
            calls.append(contact_id)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr(reveal, "_reveal_person", _reveal_person)

    stub.calls = calls
    return stub


async def test_reveal_spends_one_credit(usage, reveal_person):
    reveal_person(True)

    result = await contacts.reveal(FakeSession(make_row()), USER, 40)

    assert usage.used == 1 and usage.refunds == 0
    assert result.credits.used == 1 and result.credits.total == 50


async def test_an_already_revealed_contact_is_free(usage, reveal_person):
    reveal_person(True)

    await contacts.reveal(FakeSession(make_row(revealed=True)), USER, 40)

    assert usage.used == 0 and reveal_person.calls == []


async def test_reveal_refunds_when_someone_else_revealed_first(usage, reveal_person):
    reveal_person(False)

    await contacts.reveal(FakeSession(make_row()), USER, 40)

    assert usage.used == 0 and usage.refunds == 1


async def test_reveal_refunds_when_apollo_fails(usage, reveal_person):
    reveal_person(ApolloError("Apollo People Enrichment failed (500)"))

    with pytest.raises(ApolloError):
        await contacts.reveal(FakeSession(make_row()), USER, 40)

    assert usage.used == 0 and usage.refunds == 1


async def test_reveal_of_someone_elses_contact_is_not_found(usage):
    with pytest.raises(contacts.ContactNotFound):
        await contacts.reveal(FakeSession(None), USER, 40)

    assert usage.used == 0


async def test_found_contacts_are_revealed_until_credits_run_out(monkeypatch):
    calls = []
    outcomes = {
        1: None,
        2: ApolloError("Apollo People Enrichment failed (500)"),
        3: None,
        4: credits.CreditLimitReached("Out of credits"),
        5: None,
    }

    async def reveal_contact(db, user_id, contact_id, domain):
        calls.append((contact_id, domain))
        if outcomes[contact_id]:
            raise outcomes[contact_id]

    monkeypatch.setattr(reveal, "reveal_contact", reveal_contact)
    revealed = await contact_finder.reveal_found(
        None, USER, [1, 2, 3, 4, 5], "acme.com"
    )

    assert revealed == 2
    assert calls == [(1, "acme.com"), (2, "acme.com"), (3, "acme.com"), (4, "acme.com")]


async def test_revealing_without_credits_never_calls_apollo(usage, reveal_person):
    reveal_person(True)
    usage.limit = 0

    with pytest.raises(credits.CreditLimitReached):
        await reveal.reveal_contact(FakeSession(None), USER, 20, "acme.com")

    assert reveal_person.calls == [] and usage.refunds == 0


def test_apply_match_keeps_only_verified_emails():
    _, person_row, _, _ = make_row()

    reveal._apply_match(
        person_row,
        {
            "first_name": "Priya",
            "last_name": "Sharma",
            "email": "guess@acme.com",
            "email_status": "extrapolated",
            "linkedin_url": "javascript:alert(1)",
        },
    )

    assert person_row.revealed_at is not None
    assert person_row.last_name == "Sharma"
    assert person_row.email is None and person_row.linkedin_url is None


@pytest.fixture
def client():
    async def no_db():
        yield None

    app.dependency_overrides[get_current_user_claims] = lambda: UserClaims(
        user_id=USER, user_email="user@example.com"
    )
    app.dependency_overrides[get_async_db] = no_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "payload",
    [
        {"apollo_org_id": "not-an-id"},
        {"apollo_org_id": ORG, "roles": "backend engineer"},
    ],
)
def test_bad_add_requests_are_rejected(client, payload):
    assert client.post("/v1/outreach/companies", json=payload).status_code == 422


def test_bad_contact_type_is_rejected(client):
    assert client.get("/v1/contacts?type=ceo").status_code == 422


def test_a_cursor_round_trips_the_sort_key():
    link, _, _, _ = make_row()

    assert contacts.decode_cursor(contacts.encode_cursor(link)) == (
        85,
        link.found_at,
        40,
    )


@pytest.mark.parametrize("cursor", ["not-base64!", "", "YWJj", "MXx4fDI"])
def test_a_malformed_cursor_is_rejected(client, cursor):
    assert client.get("/v1/contacts", params={"cursor": cursor}).status_code == 400


@pytest.mark.parametrize("limit", [0, -1, contacts.MAX_PAGE_SIZE + 1])
def test_an_out_of_range_page_size_is_rejected(client, limit):
    assert client.get("/v1/contacts", params={"limit": limit}).status_code == 422


def test_outreach_routes_need_a_signed_in_user():
    with TestClient(app) as anonymous:
        assert (
            anonymous.post(
                "/v1/outreach/companies", json={"apollo_org_id": ORG}
            ).status_code
            == 401
        )
        assert anonymous.get("/v1/outreach/companies").status_code == 401
        assert anonymous.get("/v1/contacts").status_code == 401
        assert anonymous.post("/v1/contacts/1/reveal").status_code == 401
        assert anonymous.get("/v1/credits").status_code == 401
