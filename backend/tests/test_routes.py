import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.api_services import company_search
from services.hunt import apollo
from api.dependencies.authenticate import get_current_user_claims
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db
from tests.conftest import BLANK_FILTERS, make_filters

FILTERS = make_filters(hiring_locations=["dubai"], job_title_signals=["sales manager"])


async def no_db():
    yield None


@pytest.fixture
def client(monkeypatch):
    llm_calls = []

    async def generate_filters(query, user_id, profile=None):
        llm_calls.append(query)
        return FILTERS

    async def search_page(filters, page):
        return [{"id": f"{i:024x}", "name": f"Co {i}"} for i in range(100)], 100, 150

    async def get_job_postings(org_id):
        return [{"title": "Sales Manager", "posted_at": "2026-10-01"}, {"title": "Engineer"}]

    monkeypatch.setattr(company_search, "generate_filters", generate_filters)
    monkeypatch.setattr(apollo, "search_page", search_page)
    monkeypatch.setattr(apollo, "get_job_postings", get_job_postings)

    app.dependency_overrides[get_current_user_claims] = lambda: UserClaims(
        user_id=1, user_email="user@example.com"
    )
    app.dependency_overrides[get_async_db] = no_db
    with TestClient(app) as test_client:
        test_client.llm_calls = llm_calls
        yield test_client
    app.dependency_overrides.clear()


def test_search_then_load_more_reuses_the_filters(client):
    first = client.post("/v1/companies/search", json={"query": "sales in dubai"})
    body = first.json()
    second = client.post(
        "/v1/companies/search",
        json={"query": "sales in dubai", "page": 2, "filters": body["filters"]},
    )

    assert first.status_code == 200
    assert len(body["rows"]) == 100 and body["has_more"] and body["credits_left"] == 49
    assert second.status_code == 200 and not second.json()["has_more"]
    assert client.llm_calls == ["sales in dubai"]


@pytest.mark.parametrize(
    "payload, status",
    [
        ({"query": "  "}, 400),
        ({"query": "x", "filters": BLANK_FILTERS}, 400),
        ({"query": "x", "page": 0}, 422),
        ({"query": "x" * 1001}, 422),
        ({"query": "x", "filters": {**BLANK_FILTERS, "market_segments": ["ecommerce"]}}, 422),
    ],
)
def test_bad_search_requests_are_rejected(client, payload, status):
    assert client.post("/v1/companies/search", json=payload).status_code == status


def test_an_empty_wallet_returns_429(client, usage):
    usage.limit = 0

    response = client.post("/v1/companies/search", json={"query": "sales in dubai"})

    assert response.status_code == 429
    assert response.json()["detail"] == "Out of credits"


def test_job_postings_take_repeated_role_params(client):
    response = client.get(
        f"/v1/companies/{'a' * 24}/job-postings?role=sales+manager&role=account+executive"
    )
    body = response.json()

    assert response.status_code == 200
    assert body["postings"][0]["matches_role"] and body["matched_count"] == 1
    assert body["credits_left"] == 49


def test_job_postings_reject_a_malformed_company_id(client):
    assert client.get("/v1/companies/not-an-id/job-postings").status_code == 422


def test_routes_need_a_signed_in_user():
    with TestClient(app) as anonymous:
        assert anonymous.post("/v1/companies/search", json={"query": "x"}).status_code == 401
        assert anonymous.get(f"/v1/companies/{'a' * 24}/job-postings").status_code == 401
