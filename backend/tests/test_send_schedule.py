from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from api.api_services import outreach_settings as api_outreach_settings
from api.dependencies.authenticate import get_current_user_claims
from api.main import app
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db
from models.company import Company
from models.contact import Contact
from models.outreach_settings import OutreachSettings
from models.user_contact import UserContact
from services.outreach import eligibility, email_contacting, settings as outreach_settings
from services.outreach.country_business_hours import (
    COUNTRY_BUSINESS_HOURS,
    DEFAULT_BUSINESS_HOURS,
    OTHER_COUNTRIES_KEY,
    get_business_hours,
    is_country_send_allowed,
)
from services.outreach.eligibility import Lead
from tasks.handlers import proposal_auto_send

pytestmark = pytest.mark.anyio

USER = 1

MONDAY = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
WEDNESDAY = datetime(2026, 11, 11, 6, 0, tzinfo=timezone.utc)
FRIDAY = datetime(2026, 11, 13, 6, 0, tzinfo=timezone.utc)
FRIDAY_MIDDAY = datetime(2026, 11, 13, 13, 0, tzinfo=timezone.utc)
SATURDAY = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
TUESDAY = datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc)


def test_every_country_keeps_the_hours_its_rule_gives_it():
    gulf = ("United Arab Emirates", "Saudi Arabia", "Egypt", "Algeria", "Yemen", "Qatar")
    for name in gulf:
        cfg = COUNTRY_BUSINESS_HOURS[name]
        assert (cfg["start_hour"], cfg["end_hour"], cfg["default_days"]) == (8, 16, [1, 2, 3, 4, 7])
    for name in ("Israel", "Jordan"):
        cfg = COUNTRY_BUSINESS_HOURS[name]
        assert (cfg["start_hour"], cfg["end_hour"], cfg["default_days"]) == (8, 17, [1, 2, 3, 4, 7])
    usa = COUNTRY_BUSINESS_HOURS["United States"]
    assert (usa["start_hour"], usa["end_hour"], usa["default_days"]) == (8, 20, [1, 2, 3, 4, 5, 7])
    germany = COUNTRY_BUSINESS_HOURS["Germany"]
    assert (germany["start_hour"], germany["end_hour"], germany["default_days"]) == (
        8,
        17,
        [1, 2, 3, 4, 5, 7],
    )


def test_saturday_is_the_only_day_off_in_the_standard_week():
    assert COUNTRY_BUSINESS_HOURS["Germany"]["default_days"] == [1, 2, 3, 4, 5, 7]
    assert 6 not in COUNTRY_BUSINESS_HOURS["Germany"]["default_days"]
    assert 7 in COUNTRY_BUSINESS_HOURS["Germany"]["default_days"]


@pytest.mark.parametrize(
    "country",
    ["United Arab Emirates", "united arab emirates", "  UNITED ARAB EMIRATES  ", "Dubai, United Arab Emirates"],
)
def test_every_spelling_of_a_country_lands_on_one_row(country):
    key, cfg = get_business_hours(country)
    assert key == "United Arab Emirates"
    assert cfg["timezone"] == "Asia/Dubai"


@pytest.mark.parametrize("country", ["Narnia", None, "", "   "])
def test_an_unresolvable_country_falls_back_to_other_countries(country):
    key, cfg = get_business_hours(country)
    assert key == OTHER_COUNTRIES_KEY
    assert cfg is DEFAULT_BUSINESS_HOURS
    assert cfg["timezone"] is None


def test_the_longest_country_name_in_a_location_string_wins():
    assert get_business_hours("Atlanta, Georgia, United States")[0] == "United States"
    assert get_business_hours("Lagos, Nigeria")[0] == "Nigeria"
    assert get_business_hours("Niamey, Niger")[0] == "Niger"
    assert get_business_hours("Pago Pago, American Samoa")[0] == "American Samoa"


def test_a_country_name_inside_a_longer_word_is_not_a_match():
    assert get_business_hours("Chadwick Heights")[0] == OTHER_COUNTRIES_KEY


@pytest.mark.parametrize(
    "country,now,allowed",
    [
        ("United Arab Emirates", WEDNESDAY, True),
        ("Dubai, United Arab Emirates", WEDNESDAY, True),
        ("united arab emirates", FRIDAY, False),
        ("Germany", datetime(2026, 11, 9, 16, 30, tzinfo=timezone.utc), False),
        ("Narnia", SATURDAY, False),
        (None, TUESDAY, True),
    ],
)
def test_the_gate_matches_the_recipients_local_clock(country, now, allowed):
    assert is_country_send_allowed(country, {}, now) is allowed


def test_a_us_window_shifts_by_an_hour_across_the_dst_boundary():
    during_edt = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    during_est = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)

    assert is_country_send_allowed("United States", {}, during_edt) is True
    assert is_country_send_allowed("United States", {}, during_est) is False


def test_end_hour_is_exclusive():
    just_inside = datetime(2026, 11, 9, 15, 59, tzinfo=timezone.utc)
    on_the_hour = datetime(2026, 11, 9, 16, 0, tzinfo=timezone.utc)

    assert is_country_send_allowed("Germany", {}, just_inside) is True
    assert is_country_send_allowed("Germany", {}, on_the_hour) is False


def test_an_override_replaces_the_default_days():
    assert is_country_send_allowed("Germany", {"Germany": [6]}, MONDAY) is False
    assert is_country_send_allowed("Germany", {"Germany": [1]}, MONDAY) is True


def test_a_stored_empty_day_list_falls_back_instead_of_blocking_every_day():
    assert is_country_send_allowed("Germany", {"Germany": []}, MONDAY) is True


def test_other_countries_is_overridable_by_its_key():
    assert is_country_send_allowed("Narnia", {OTHER_COUNTRIES_KEY: [6]}, SATURDAY) is True


def _lead(contact_id: int, country: Optional[str], found_at: datetime) -> Lead:
    contact = Contact(
        company_id=1,
        first_name=f"P{contact_id}",
        country=country,
        email=f"p{contact_id}@acme.test",
    )
    contact.id = contact_id
    user_contact = UserContact(
        user_id=USER,
        contact_id=contact_id,
        user_company_id=1,
        type="recruiter",
        relevance=1,
    )
    user_contact.id = contact_id
    user_contact.found_at = found_at
    return Lead(
        user_contact=user_contact,
        contact=contact,
        company=Company(apollo_org_id="a" * 24, name="Acme"),
        roles=[],
        locations=[],
    )


class _NoSession:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


async def _keep_going() -> bool:
    return True


@pytest.fixture
def outreach_run(monkeypatch):
    monkeypatch.setattr(email_contacting, "AsyncSessionLocal", _NoSession)
    monkeypatch.setattr(email_contacting, "get_email_provider", lambda mailbox: object())

    async def never_matches(db, query):
        return False

    monkeypatch.setattr(eligibility, "any_match", never_matches)

    def build(schedule, leads):
        cursors = []

        async def first_touch_page(db, user_id, own_domain, after, limit):
            cursors.append(after)
            if after is None:
                return leads[:limit]
            return []

        monkeypatch.setattr(eligibility, "first_touch_page", first_touch_page)

        ctx = SimpleNamespace(
            settings=SimpleNamespace(max_follow_ups=2, follow_up_interval_days=3, enabled=True),
            mailbox=SimpleNamespace(
                id=1,
                email="me@acme.test",
                warmup_started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                provider="gmail",
            ),
        )
        run = email_contacting._OutreachRun(
            USER, ctx, _keep_going, stop_when_disabled=False, schedule=schedule, paced=False
        )
        sent = []

        async def first_touch(user_contact_id, follow_ups_due):
            sent.append(user_contact_id)
            return email_contacting._Outcome.SENT

        monkeypatch.setattr(run, "_first_touch", first_touch)
        return run, sent, cursors

    return build


def _full_page(country):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [_lead(i, country, start + timedelta(minutes=i)) for i in range(1, 11)]


async def test_a_page_where_every_recipient_is_out_of_hours_still_ends_the_run(outreach_run, monkeypatch):
    leads = _full_page("Germany")
    run, sent, cursors = outreach_run({"enabled": True, "overrides": {}}, leads)
    monkeypatch.setattr(email_contacting, "datetime", _FrozenClock(SATURDAY))

    await run.first_touches()

    assert sent == []
    assert run.skipped_by_schedule == 10
    last = leads[-1].user_contact
    assert cursors == [None, (last.found_at, last.id)]


async def test_a_recipient_held_by_the_schedule_is_sent_on_a_later_run(outreach_run, monkeypatch):
    leads = _full_page("Germany")
    run, sent, _ = outreach_run({"enabled": True, "overrides": {}}, leads)
    monkeypatch.setattr(email_contacting, "datetime", _FrozenClock(SATURDAY))
    await run.first_touches()
    assert sent == []

    later, sent_later, _ = outreach_run({"enabled": True, "overrides": {}}, leads)
    monkeypatch.setattr(email_contacting, "datetime", _FrozenClock(MONDAY))
    await later.first_touches()

    assert sent_later == [lead.user_contact.id for lead in leads]
    assert later.skipped_by_schedule == 0


async def test_with_the_switch_off_no_country_is_ever_consulted(outreach_run, monkeypatch):
    leads = _full_page("Germany")
    run, sent, _ = outreach_run(email_contacting.SEND_ANYTIME, leads)

    def refuse(*args, **kwargs):
        raise AssertionError("The gate ran with the sending schedule switched off")

    monkeypatch.setattr(email_contacting, "is_country_send_allowed", refuse)
    monkeypatch.setattr(email_contacting, "datetime", _FrozenClock(SATURDAY))

    await run.first_touches()

    assert sent == [lead.user_contact.id for lead in leads]
    assert run.skipped_by_schedule == 0


async def test_only_the_countries_outside_their_window_are_held(outreach_run, monkeypatch):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    leads = [
        _lead(1, "Germany", start),
        _lead(2, "United Arab Emirates", start + timedelta(minutes=1)),
        _lead(3, "Narnia", start + timedelta(minutes=2)),
    ]
    run, sent, _ = outreach_run({"enabled": True, "overrides": {}}, leads)
    monkeypatch.setattr(email_contacting, "datetime", _FrozenClock(FRIDAY_MIDDAY))

    await run.first_touches()

    assert sent == [1, 3]
    assert run.skipped_by_schedule == 1


class _FrozenClock:
    def __init__(self, now: datetime):
        self._now = now

    def now(self, tz=None):
        return self._now


class _SettingsSession:
    def __init__(self, row):
        self.row = row
        self.commits = 0
        self.locked = False

    async def get(self, model, pk, with_for_update=False, populate_existing=False):
        if with_for_update:
            self.locked = True
        return self.row

    async def commit(self):
        self.commits += 1

    async def execute(self, statement):
        raise AssertionError("A settings write should not need a raw statement")


async def test_saving_one_countrys_days_keeps_the_countries_already_stored():
    row = SimpleNamespace(
        email_send_schedule={"Germany": [1, 2]}, email_send_schedule_enabled=True
    )
    db = _SettingsSession(row)

    await outreach_settings.set_email_send_schedule_days(
        db, USER, "United Arab Emirates", [1, 2, 3, 4, 7]
    )

    assert row.email_send_schedule == {
        "Germany": [1, 2],
        "United Arab Emirates": [1, 2, 3, 4, 7],
    }
    assert db.locked is True
    assert db.commits == 1


async def test_saving_days_onto_a_null_column_starts_a_fresh_map():
    row = SimpleNamespace(email_send_schedule=None, email_send_schedule_enabled=None)
    db = _SettingsSession(row)

    await outreach_settings.set_email_send_schedule_days(db, USER, "Germany", [1])

    assert row.email_send_schedule == {"Germany": [1]}


class _ScheduleReadSession:
    def __init__(self, row):
        self.row = row

    async def execute(self, statement):
        row = self.row

        class Result:
            def first(self_inner):
                return row

        return Result()


def test_a_new_users_sending_schedule_starts_on():
    settings = OutreachSettings(user_id=USER)

    assert settings.email_send_schedule_enabled is True
    assert settings.email_send_schedule == {}


def test_users_who_predate_the_column_are_switched_on_by_the_migration():
    column = OutreachSettings.__table__.c.email_send_schedule_enabled

    assert str(column.server_default.arg).lower() == "true"


async def test_a_null_schedule_column_reads_as_off_with_no_overrides():
    schedule = await outreach_settings.get_email_send_schedule(
        _ScheduleReadSession((None, None)), USER
    )

    assert schedule == {"enabled": False, "overrides": {}}


async def test_a_user_with_no_settings_row_reads_as_off():
    schedule = await outreach_settings.get_email_send_schedule(
        _ScheduleReadSession(None), USER
    )

    assert schedule == {"enabled": False, "overrides": {}}


class _DueSession:
    def __init__(self, rows):
        self.rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, statement):
        rows = self.rows

        class Result:
            def tuples(self_inner):
                class Tuples:
                    def all(self_deep):
                        return rows

                return Tuples()

        return Result()


@pytest.fixture
def auto_send(monkeypatch):
    def build(rows, now):
        monkeypatch.setattr(proposal_auto_send, "AsyncSessionLocal", lambda: _DueSession(rows))
        monkeypatch.setattr(proposal_auto_send, "datetime", _FrozenClock(now))
        sent: list[int] = []
        waited: list[int] = []

        async def send(user_id, proposal_id):
            sent.append(proposal_id)

        async def wait_for_user(proposal_id):
            waited.append(proposal_id)

        monkeypatch.setattr(proposal_auto_send.proposals, "send", send)
        monkeypatch.setattr(proposal_auto_send, "_wait_for_user", wait_for_user)
        return sent, waited

    return build


async def test_an_auto_reply_outside_local_hours_is_held_with_no_state_change(auto_send):
    sent, waited = auto_send([(7, USER, True, True, {}, "Germany")], SATURDAY)

    await proposal_auto_send.handle({})

    assert sent == []
    assert waited == []


async def test_a_held_auto_reply_goes_out_once_the_window_opens(auto_send):
    rows = [(7, USER, True, True, {}, "Germany")]
    sent, _ = auto_send(rows, SATURDAY)
    await proposal_auto_send.handle({})
    assert sent == []

    sent_later, _ = auto_send(rows, MONDAY)
    await proposal_auto_send.handle({})

    assert sent_later == [7]


async def test_auto_replies_ignore_local_hours_while_the_schedule_is_off(auto_send):
    sent, _ = auto_send([(7, USER, True, False, {}, "Germany"), (8, USER, True, None, None, None)], SATURDAY)

    await proposal_auto_send.handle({})

    assert sent == [7, 8]


async def test_a_draft_the_user_never_armed_still_goes_back_to_them(auto_send):
    sent, waited = auto_send([(7, USER, False, True, {}, "Germany")], SATURDAY)

    await proposal_auto_send.handle({})

    assert sent == []
    assert waited == [7]


class _RowsSession:
    def __init__(self, settings_row, countries):
        self.settings_row = settings_row
        self.countries = countries
        self.calls = 0

    async def get(self, model, pk, **options):
        return SimpleNamespace(user_id=pk)

    async def execute(self, statement):
        self.calls += 1
        settings_row, countries = self.settings_row, self.countries

        class Result:
            def first(self_inner):
                return settings_row

            def scalars(self_inner):
                class Scalars:
                    def all(self_deep):
                        return countries

                return Scalars()

        return Result()


async def test_only_the_countries_in_the_users_own_contacts_get_a_row():
    db = _RowsSession((True, {}), ["Germany", "India", "Germany"])

    out = await api_outreach_settings.read_send_schedule(db, USER)

    assert out.enabled is True
    assert [row.country for row in out.rows] == ["Germany", "India"]


async def test_every_spelling_of_one_country_collapses_to_a_single_row():
    db = _RowsSession(
        (True, {}),
        ["United Arab Emirates", "united arab emirates", "Dubai, United Arab Emirates"],
    )

    out = await api_outreach_settings.read_send_schedule(db, USER)

    assert [row.country for row in out.rows] == ["United Arab Emirates"]
    assert out.rows[0].days == [1, 2, 3, 4, 7]
    assert (out.rows[0].start_hour, out.rows[0].end_hour) == (8, 16)
    assert out.rows[0].timezone == "Asia/Dubai"


async def test_unresolved_countries_share_one_other_countries_row_sorted_last():
    db = _RowsSession((False, {}), ["Narnia", None, "Germany", "Atlantis"])

    out = await api_outreach_settings.read_send_schedule(db, USER)

    assert [row.country for row in out.rows] == ["Germany", "Other countries"]
    assert out.rows[-1].timezone is None


async def test_rows_follow_the_order_of_the_country_table():
    db = _RowsSession((True, {}), ["Germany", "Australia", "United States", "India"])

    out = await api_outreach_settings.read_send_schedule(db, USER)

    assert [row.country for row in out.rows] == ["Australia", "Germany", "India", "United States"]


async def test_a_stored_override_is_what_the_row_shows():
    db = _RowsSession((True, {"Germany": [1, 2]}), ["Germany"])

    out = await api_outreach_settings.read_send_schedule(db, USER)

    assert out.rows[0].days == [1, 2]


def test_the_other_countries_label_round_trips_to_its_storage_key():
    assert api_outreach_settings._schedule_key("Other countries") == OTHER_COUNTRIES_KEY
    assert api_outreach_settings._schedule_key("Germany") == "Germany"


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
        {"country": "Germany", "days": []},
        {"days": [1]},
        {"country": "Germany"},
        {"country": "Germany", "days": [0]},
        {"country": "Germany", "days": [8]},
        {},
    ],
)
def test_a_malformed_schedule_patch_is_rejected(client, payload):
    assert client.patch("/v1/outreach/settings/email-send-schedule", json=payload).status_code == 422


def test_an_unknown_country_is_named_in_the_error(client):
    response = client.patch(
        "/v1/outreach/settings/email-send-schedule", json={"country": "Atlantis", "days": [1]}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Unknown country 'Atlantis'"


def test_the_sending_schedule_needs_a_signed_in_user():
    with TestClient(app) as anonymous:
        assert anonymous.get("/v1/outreach/settings/email-send-schedule").status_code == 401
        assert (
            anonymous.patch(
                "/v1/outreach/settings/email-send-schedule", json={"enabled": True}
            ).status_code
            == 401
        )
