import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("CLERK_FRONTEND_API", "https://clerk.example.test")

import json
from typing import Any

import httpx
import pytest

from api.api_services import company_search, outreach
from services import career_profiles, hunter, openai_client, s3, tavily, user_profiles
from services.hunt import apollo, apollo_cache, contact_finder, hunt_filters, targets
from services.hunt import credits
from services.schemas.company import CompanyFilters
from services.schemas.user_profile import Preferences
from services.schemas.career_profile import CareerProfile

BLANK_FILTERS: dict[str, Any] = dict(
    hiring_locations=[],
    company_locations=[],
    employee_ranges=[],
    keyword_tags=[],
    market_segments=[],
    job_title_signals=[],
    min_active_job_postings=None,
    job_posted_within_days=None,
    founded_year_min=None,
    founded_year_max=None,
)


BLANK_PROFILE: dict[str, Any] = dict(
    current_title=None,
    seniority=None,
    function=None,
    top_skills=[],
    industries=[],
    location=None,
    open_to_locations=[],
    company_size_history=[],
)


def make_filters(**fields) -> CompanyFilters:
    return CompanyFilters(**{**BLANK_FILTERS, **fields})


def make_profile(**fields) -> CareerProfile:
    return CareerProfile(**{**BLANK_PROFILE, **fields})


def use_apollo_transport(monkeypatch, handler) -> None:
    monkeypatch.setattr(
        apollo,
        "_client",
        httpx.AsyncClient(
            base_url="https://api.apollo.io/api/v1", transport=httpx.MockTransport(handler)
        ),
    )


def use_hunter_transport(monkeypatch, handler) -> None:
    monkeypatch.setattr(
        hunter,
        "_client",
        httpx.AsyncClient(base_url="https://api.hunter.io/v2", transport=httpx.MockTransport(handler)),
    )


def use_tavily_transport(monkeypatch, handler) -> None:
    monkeypatch.setattr(
        tavily,
        "_client",
        httpx.AsyncClient(base_url="https://api.tavily.com", transport=httpx.MockTransport(handler)),
    )


class FakeUsage:
    def __init__(self, limit: int = 50):
        self.limit = limit
        self.used = 0
        self.refunds = 0

    async def reserve_credit(self, db, user_id, purpose):
        if self.used >= self.limit:
            raise credits.CreditLimitReached("Out of credits")
        self.used += 1

    async def refund_credit(self, db, user_id):
        self.used -= 1
        self.refunds += 1

    async def credits_left(self, db, user_id):
        return self.limit - self.used

    async def wallet(self, db, user_id):
        return self.limit - self.used, self.limit


class FakeProfiles:
    def __init__(self):
        self.data: dict[int, CareerProfile] = {}

    async def get(self, db, user_id):
        return self.data.get(user_id)

    async def upsert(self, db, user_id, profile, source_resume_id=None):
        self.data[user_id] = profile
        return profile


class FakePreferences:
    def __init__(self):
        self.data: dict[int, Preferences] = {}

    async def get_preferences(self, db, user_id):
        return self.data.get(user_id) or Preferences()


class FakeStore:
    def __init__(self):
        self.data: dict = {}

    async def get(self, db, key):
        return self.data.get(key)

    async def put(self, db, key, payload):
        self.data[key] = json.loads(json.dumps(payload))

    async def delete_expired(self):
        return 0


class RefuseS3:
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected S3 call: {name}")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    def refuse(request):
        raise AssertionError(f"Unexpected Apollo call: {request.url}")

    def refuse_hunter(request):
        raise AssertionError(f"Unexpected Hunter call: {request.url}")

    def refuse_tavily(request):
        raise AssertionError(f"Unexpected Tavily call: {request.url}")

    use_apollo_transport(monkeypatch, refuse)
    use_hunter_transport(monkeypatch, refuse_hunter)
    use_tavily_transport(monkeypatch, refuse_tavily)
    monkeypatch.setattr(apollo, "RETRY_DELAYS", (0, 0))
    monkeypatch.setenv("APOLLO_API_KEY", "test")
    monkeypatch.delenv("HUNTER_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(openai_client, "_client", None)
    monkeypatch.setattr(s3, "_session", RefuseS3())
    for module in (company_search, contact_finder, hunt_filters, outreach):
        module.clear_caches()
    yield
    for module in (company_search, contact_finder, hunt_filters, outreach):
        module.clear_caches()


@pytest.fixture(autouse=True)
def usage(monkeypatch) -> FakeUsage:
    fake = FakeUsage()
    for name in ("reserve_credit", "refund_credit", "credits_left", "wallet"):
        monkeypatch.setattr(credits, name, getattr(fake, name))
    return fake


class FakeCompanies:
    def __init__(self):
        self.ok = True
        self.saves: list[int] = []

    async def save_companies(self, db, rows):
        self.saves.append(len(rows))
        return self.ok


@pytest.fixture(autouse=True)
def companies(monkeypatch) -> FakeCompanies:
    fake = FakeCompanies()
    monkeypatch.setattr(targets, "save_companies", fake.save_companies)
    return fake


@pytest.fixture(autouse=True)
def store(monkeypatch) -> FakeStore:
    fake = FakeStore()
    for name in ("get", "put", "delete_expired"):
        monkeypatch.setattr(apollo_cache, name, getattr(fake, name))
    return fake


@pytest.fixture(autouse=True)
def profiles(monkeypatch) -> FakeProfiles:
    fake = FakeProfiles()
    for name in ("get", "upsert"):
        monkeypatch.setattr(career_profiles, name, getattr(fake, name))
    return fake


@pytest.fixture(autouse=True)
def preferences(monkeypatch) -> FakePreferences:
    fake = FakePreferences()
    monkeypatch.setattr(user_profiles, "get_preferences", fake.get_preferences)
    return fake
