from datetime import datetime, timedelta, timezone

import pytest

from services.hunt import auto_hunt, hunt_filters
from services.hunt.company_search import MAX_PAGES
from services.schemas.company import CompanyRow
from services.schemas.user_profile import Culture, Preferences, TargetLocation
from tests.conftest import make_filters, make_profile

pytestmark = pytest.mark.anyio

USER = 1


def targets(**fields) -> Preferences:
    return Preferences(**fields)


def row(org_id: str) -> CompanyRow:
    return CompanyRow(
        apollo_org_id=org_id,
        company_name=org_id,
        domain=f"{org_id}.com",
        linkedin_url=None,
        linkedin_jobs_url=None,
        logo_url=None,
        founded_year=None,
    )


def test_targets_become_a_description():
    described = hunt_filters.describe(
        targets(
            roles=["Backend Engineer"],
            seniority=["Senior", "Staff"],
            locations=[
                TargetLocation(country="India", city="Bengaluru"),
                TargetLocation(country="Singapore"),
            ],
            remote="apac",
            culture=Culture(company_stage=["seed", "series A"]),
        )
    )
    assert "Senior/Staff Backend Engineer roles" in described
    assert "Bengaluru, India or Singapore" in described
    assert "seed or series A companies" in described
    assert "anywhere in APAC" in described


def test_a_country_only_target_still_describes_a_place():
    described = hunt_filters.describe(
        targets(locations=[TargetLocation(country="United Arab Emirates")])
    )
    assert described == "Companies hiring in United Arab Emirates."


def test_remote_alone_is_not_a_description():
    assert hunt_filters.describe(targets(remote="global")) == ""


async def test_filters_come_from_targets(monkeypatch, preferences):
    asked = []

    async def generate_filters(query, user_id, profile):
        asked.append((query, profile))
        return make_filters(job_title_signals=["backend engineer"], hiring_locations=["india"])

    monkeypatch.setattr(hunt_filters, "generate_filters", generate_filters)
    preferences.data[USER] = targets(
        roles=["Backend Engineer"], locations=[TargetLocation(country="India")]
    )

    found = await hunt_filters.hunt_filters(None, USER)

    assert found is not None
    filters, key = found
    assert filters.job_title_signals == ["backend engineer"]
    assert key
    assert "Backend Engineer" in asked[0][0]


async def test_the_resume_hunts_when_there_are_no_targets(monkeypatch, profiles):
    asked = []

    async def generate_filters(query, user_id, profile):
        asked.append((query, profile))
        return make_filters(job_title_signals=["backend engineer"])

    monkeypatch.setattr(hunt_filters, "generate_filters", generate_filters)
    profiles.data[USER] = make_profile(current_title="Backend Engineer")

    found = await hunt_filters.hunt_filters(None, USER)

    assert found is not None
    assert asked[0][0] == ""
    assert asked[0][1] is not None


async def test_no_targets_and_no_resume_means_nothing_to_hunt(monkeypatch):
    async def refuse(query, user_id, profile):
        raise AssertionError("The filter LLM shouldn't be called with nothing to search on")

    monkeypatch.setattr(hunt_filters, "generate_filters", refuse)

    assert await hunt_filters.hunt_filters(None, USER) is None


async def test_empty_filters_mean_nothing_to_hunt(monkeypatch, preferences):
    async def generate_filters(query, user_id, profile):
        return make_filters()

    monkeypatch.setattr(hunt_filters, "generate_filters", generate_filters)
    preferences.data[USER] = targets(roles=["Backend Engineer"])

    assert await hunt_filters.hunt_filters(None, USER) is None


async def test_the_same_targets_call_the_llm_once(monkeypatch, preferences):
    calls = []

    async def generate_filters(query, user_id, profile):
        calls.append(query)
        return make_filters(job_title_signals=["backend engineer"])

    monkeypatch.setattr(hunt_filters, "generate_filters", generate_filters)
    preferences.data[USER] = targets(roles=["Backend Engineer"])

    first = await hunt_filters.hunt_filters(None, USER)
    second = await hunt_filters.hunt_filters(None, USER)

    assert len(calls) == 1
    assert first is not None and second is not None
    assert first[1] == second[1]


async def test_changed_targets_regenerate_the_filters(monkeypatch, preferences):
    async def generate_filters(query, user_id, profile):
        return make_filters(job_title_signals=[query.split()[3].lower()])

    monkeypatch.setattr(hunt_filters, "generate_filters", generate_filters)

    preferences.data[USER] = targets(roles=["Backend"])
    first = await hunt_filters.hunt_filters(None, USER)
    preferences.data[USER] = targets(roles=["Frontend"])
    second = await hunt_filters.hunt_filters(None, USER)

    assert first is not None and second is not None
    assert first[1] != second[1]


async def test_knowing_there_are_targets_costs_no_llm_call(monkeypatch, preferences, profiles):
    async def refuse(query, user_id, profile):
        raise AssertionError("Checking for targets must not call the filter LLM")

    monkeypatch.setattr(hunt_filters, "generate_filters", refuse)

    assert await hunt_filters.has_targets(None, USER) is False

    preferences.data[USER] = targets(roles=["Backend Engineer"])
    assert await hunt_filters.has_targets(None, USER) is True

    preferences.data.clear()
    profiles.data[USER] = make_profile(current_title="Backend Engineer")
    assert await hunt_filters.has_targets(None, USER) is True


def test_a_hunt_is_due_24_hours_after_the_last_one(monkeypatch):
    monkeypatch.setattr(auto_hunt, "HUNT_EVERY", timedelta(hours=24))
    now = datetime(2026, 11, 9, 14, 30, tzinfo=timezone.utc)

    assert auto_hunt.due_at(now) == datetime(2026, 11, 8, 14, 30, tzinfo=timezone.utc)

    clause = auto_hunt.is_due(now)
    compiled = str(clause.compile(compile_kwargs={"literal_binds": True}))
    assert "last_run_at IS NULL" in compiled
    assert "2026-11-08 14:30:00" in compiled


def test_a_hunt_is_not_due_again_the_moment_the_clock_rolls_over(monkeypatch):
    monkeypatch.setattr(auto_hunt, "HUNT_EVERY", timedelta(hours=24))
    ran_at = datetime(2026, 11, 8, 23, 50, tzinfo=timezone.utc)

    just_after_midnight = datetime(2026, 11, 9, 0, 10, tzinfo=timezone.utc)
    assert auto_hunt.due_at(just_after_midnight) < ran_at

    a_day_later = datetime(2026, 11, 9, 23, 55, tzinfo=timezone.utc)
    assert auto_hunt.due_at(a_day_later) > ran_at


def test_the_interval_is_configurable(monkeypatch):
    monkeypatch.setattr(auto_hunt, "HUNT_EVERY", timedelta(hours=6))
    now = datetime(2026, 11, 9, 14, 30, tzinfo=timezone.utc)
    assert auto_hunt.due_at(now) == datetime(2026, 11, 9, 8, 30, tzinfo=timezone.utc)


async def test_the_hunt_only_looks_at_recent_postings(monkeypatch, preferences):
    async def generate_filters(query, user_id, profile):
        return make_filters(job_title_signals=["backend engineer"])

    monkeypatch.setattr(hunt_filters, "generate_filters", generate_filters)
    preferences.data[USER] = targets(roles=["Backend Engineer"])

    found = await hunt_filters.hunt_filters(None, USER)

    assert found is not None
    assert found[0].job_posted_within_days == hunt_filters.DEFAULT_JOB_POSTED_WITHIN_DAYS


async def test_the_posting_window_never_hides_that_there_is_nothing_to_search(
    monkeypatch, preferences
):
    async def generate_filters(query, user_id, profile):
        return make_filters()

    monkeypatch.setattr(hunt_filters, "generate_filters", generate_filters)
    preferences.data[USER] = targets(roles=["Backend Engineer"])

    assert await hunt_filters.hunt_filters(None, USER) is None


async def test_the_posting_window_keeps_the_page_cursor_stable(monkeypatch, preferences):
    async def generate_filters(query, user_id, profile):
        return make_filters(job_title_signals=["backend engineer"])

    monkeypatch.setattr(hunt_filters, "generate_filters", generate_filters)
    preferences.data[USER] = targets(roles=["Backend Engineer"])

    first = await hunt_filters.hunt_filters(None, USER)
    hunt_filters.clear_caches()
    second = await hunt_filters.hunt_filters(None, USER)

    assert first is not None and second is not None
    assert first[1] == second[1]


async def test_an_explicit_posting_window_is_not_overridden(monkeypatch, preferences):
    async def generate_filters(query, user_id, profile):
        return make_filters(job_title_signals=["backend engineer"], job_posted_within_days=7)

    monkeypatch.setattr(hunt_filters, "generate_filters", generate_filters)
    preferences.data[USER] = targets(roles=["Backend Engineer"])

    found = await hunt_filters.hunt_filters(None, USER)

    assert found is not None
    assert found[0].job_posted_within_days == 7


async def test_the_budget_becomes_a_reserve(usage):
    usage.limit, usage.used = 50, 10

    assert await auto_hunt.reserve_for(None, USER, 30) == 10
    assert await auto_hunt.reserve_for(None, USER, 40) == 0
    assert await auto_hunt.reserve_for(None, USER, 0) == 40
    assert await auto_hunt.reserve_for(None, USER, 250) == 0


def test_the_hunt_searches_where_the_jobs_are():
    assert auto_hunt.locations_for(
        make_filters(hiring_locations=["dubai"], company_locations=["india"])
    ) == ["dubai"]
    assert auto_hunt.locations_for(make_filters(company_locations=["india"])) == ["india"]


class FakeSweep:
    def __init__(self, monkeypatch, pages, *, credits=50, taken=(), reserve=0):
        self.pages = pages
        self.credits = credits
        self.taken = set(taken)
        self.reserve = reserve
        self.searched: list[str] = []
        self.fetched: list[int] = []

        async def fetch_page(db, filters, page, user_id):
            self.fetched.append(page)
            self.credits -= 1
            rows = self.pages.get(page, [])
            return rows, page < max(self.pages)

        async def already_targeted(db, user_id, org_ids):
            return {org_id for org_id in org_ids if org_id in self.taken}

        async def search_company(db, user_id, row, filters):
            self.searched.append(row.apollo_org_id)
            self.credits -= 2
            return 2

        async def credits_left(db, user_id):
            return self.credits

        monkeypatch.setattr(auto_hunt.company_search, "fetch_page", fetch_page)
        monkeypatch.setattr(auto_hunt, "_already_targeted", already_targeted)
        monkeypatch.setattr(auto_hunt, "_search_company", search_company)
        monkeypatch.setattr(auto_hunt.credits, "credits_left", credits_left)

    def sweep(self, page=1):
        return auto_hunt._Sweep(None, USER, make_filters(), page, self.reserve)


async def test_a_sweep_searches_every_new_company(monkeypatch):
    fake = FakeSweep(monkeypatch, {1: [row("a"), row("b")]})
    sweep = fake.sweep()

    await sweep.run()

    assert fake.searched == ["a", "b"]
    assert sweep.companies == 2
    assert sweep.contacts == 4
    assert sweep.error is None


async def test_companies_already_being_hunted_are_skipped(monkeypatch):
    fake = FakeSweep(monkeypatch, {1: [row("a"), row("b"), row("c")]}, taken=["b"])
    sweep = fake.sweep()

    await sweep.run()

    assert fake.searched == ["a", "c"]
    assert sweep.companies == 2


async def test_a_sweep_walks_the_pages_and_wraps_at_the_end(monkeypatch):
    fake = FakeSweep(monkeypatch, {1: [row("a")], 2: [row("b")], 3: [row("c")]}, credits=200)
    sweep = fake.sweep()

    await sweep.run()

    assert fake.fetched == [1, 2, 3]
    assert sweep.page == 1


async def test_a_sweep_resumes_on_the_page_it_stopped_at(monkeypatch):
    fake = FakeSweep(monkeypatch, {1: [row("a")], 2: [row("b")], 3: [row("c")]}, credits=200)
    sweep = fake.sweep(page=3)

    await sweep.run()

    assert fake.fetched == [3]
    assert fake.searched == ["c"]


async def test_a_sweep_stops_before_it_eats_the_credit_reserve(monkeypatch):
    pages = {page: [row(f"c{page}")] for page in range(1, MAX_PAGES + 1)}
    fake = FakeSweep(monkeypatch, pages, credits=20, reserve=10)
    sweep = fake.sweep()

    await sweep.run()

    assert fake.credits >= 10
    assert sweep.error == auto_hunt.NO_CREDITS
    assert sweep.page > 1


async def test_a_sweep_spends_everything_when_the_budget_is_the_whole_allowance(monkeypatch):
    pages = {page: [row(f"c{page}")] for page in range(1, MAX_PAGES + 1)}
    fake = FakeSweep(monkeypatch, pages, credits=9, reserve=0)
    sweep = fake.sweep()

    await sweep.run()

    assert fake.credits < 3
    assert sweep.error == auto_hunt.NO_CREDITS


async def test_a_sweep_stops_at_the_page_cap(monkeypatch):
    pages = {page: [row(f"c{page}")] for page in range(1, MAX_PAGES + 2)}
    fake = FakeSweep(monkeypatch, pages, credits=1000)
    sweep = fake.sweep()

    await sweep.run()

    assert fake.fetched == list(range(1, MAX_PAGES + 1))
    assert sweep.page == 1
