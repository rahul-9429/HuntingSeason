from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from models.company import Company
from models.contact import Contact
from models.enums import MailboxStatus
from models.outreach_settings import OutreachSettings
from models.user_contact import UserContact
from services.outreach import eligibility, email_contacting, limits, pacing
from services.outreach.eligibility import Lead
from tasks import scheduler

pytestmark = pytest.mark.anyio

USER = 1
NOW = datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)


class _FrozenClock:
    def __init__(self, now: datetime):
        self._now = now

    def now(self, tz=None):
        return self._now


class _NoSession:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


async def _keep_going() -> bool:
    return True


def _settings(min_gap: int = 180, max_gap: int = 900) -> SimpleNamespace:
    return SimpleNamespace(
        min_gap_seconds=min_gap,
        max_gap_seconds=max_gap,
        enabled=True,
        max_follow_ups=2,
        follow_up_interval_days=3,
    )


def test_a_gap_lands_between_the_two_bounds():
    gaps = {pacing.next_gap(_settings(60, 90)) for _ in range(50)}

    assert gaps
    assert all(timedelta(seconds=60) <= gap <= timedelta(seconds=90) for gap in gaps)
    assert len(gaps) > 1


def test_a_longest_gap_below_the_shortest_collapses_to_the_shortest():
    assert pacing.next_gap(_settings(300, 60)) == timedelta(seconds=300)


def test_a_zero_gap_still_leaves_a_second_between_sends():
    assert pacing.next_gap(_settings(0, 0)) == timedelta(seconds=1)


@pytest.mark.parametrize(
    "next_send_at,due",
    [
        (None, True),
        (NOW - timedelta(seconds=1), True),
        (NOW, True),
        (NOW + timedelta(seconds=1), False),
    ],
)
def test_a_mailbox_is_due_only_once_its_gap_has_run_out(next_send_at, due):
    assert pacing.is_due(next_send_at, NOW) is due


def test_an_exhausted_day_waits_for_the_next_one_in_utc():
    assert pacing.next_utc_day(NOW) == datetime(2026, 11, 18, tzinfo=timezone.utc)
    late = datetime(2026, 11, 17, 23, 59, 59, tzinfo=timezone.utc)
    assert pacing.next_utc_day(late) == datetime(2026, 11, 18, tzinfo=timezone.utc)


def test_the_next_day_is_read_off_the_utc_clock_not_the_servers():
    in_sydney = datetime(2026, 11, 18, 9, 0, tzinfo=timezone(timedelta(hours=11)))

    assert pacing.next_utc_day(in_sydney) == datetime(2026, 11, 18, tzinfo=timezone.utc)


def test_a_new_users_gap_is_set_without_them_choosing_one():
    settings = OutreachSettings(user_id=USER)

    assert (settings.min_gap_seconds, settings.max_gap_seconds) == (180, 900)


def test_users_who_predate_the_columns_get_the_same_gap_from_the_migration():
    table = OutreachSettings.__table__.c

    assert str(table.min_gap_seconds.server_default.arg) == "180"
    assert str(table.max_gap_seconds.server_default.arg) == "900"


def _lead(contact_id: int, found_at: datetime) -> Lead:
    contact = Contact(
        company_id=1,
        first_name=f"P{contact_id}",
        country=None,
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


def _page(size: int = 10) -> list[Lead]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [_lead(i, start + timedelta(minutes=i)) for i in range(1, size + 1)]


@pytest.fixture
def outreach_run(monkeypatch):
    monkeypatch.setattr(email_contacting, "AsyncSessionLocal", _NoSession)
    monkeypatch.setattr(email_contacting, "get_email_provider", lambda mailbox: object())

    async def never_matches(db, query):
        return False

    monkeypatch.setattr(eligibility, "any_match", never_matches)

    def build(leads, paced):
        async def first_touch_page(db, user_id, own_domain, after, limit):
            return leads[:limit] if after is None else []

        monkeypatch.setattr(eligibility, "first_touch_page", first_touch_page)

        ctx = SimpleNamespace(
            settings=_settings(),
            mailbox=SimpleNamespace(
                id=1,
                email="me@acme.test",
                warmup_started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                provider="gmail",
            ),
        )
        run = email_contacting._OutreachRun(
            USER,
            ctx,
            _keep_going,
            stop_when_disabled=False,
            schedule=email_contacting.SEND_ANYTIME,
            paced=paced,
        )
        sent: list[int] = []

        async def first_touch(user_contact_id, follow_ups_due):
            sent.append(user_contact_id)
            run.sent_this_run = True
            return email_contacting._Outcome.SENT

        monkeypatch.setattr(run, "_first_touch", first_touch)
        return run, sent

    return build


async def test_a_paced_run_sends_one_email_and_leaves_the_rest_for_later(outreach_run):
    run, sent = outreach_run(_page(), paced=True)

    await run.first_touches()

    assert sent == [1]
    assert run.first_sent == 1


async def test_an_unpaced_run_still_works_through_the_whole_page(outreach_run):
    run, sent = outreach_run(_page(), paced=False)

    await run.first_touches()

    assert sent == [lead.user_contact.id for lead in _page()]


async def test_the_one_email_of_a_run_is_not_followed_by_a_follow_up(outreach_run, monkeypatch):
    run, _ = outreach_run(_page(), paced=True)
    await run.first_touches()

    def refuse(*args, **kwargs):
        raise AssertionError("A paced run looked for follow-ups after sending")

    monkeypatch.setattr(eligibility, "any_match", refuse)

    await run.follow_ups()


async def test_a_sent_email_pushes_the_mailbox_past_a_random_gap(outreach_run, monkeypatch):
    run, _ = outreach_run([], paced=True)
    holds: list[tuple[int, datetime]] = []

    async def hold_until(mailbox_id, when):
        holds.append((mailbox_id, when))

    async def save_send(*args, **kwargs):
        return None

    monkeypatch.setattr(pacing, "hold_until", hold_until)
    monkeypatch.setattr(run, "_save_send", save_send)
    monkeypatch.setattr(email_contacting, "datetime", _FrozenClock(NOW))

    await run._record(_lead(1, NOW), None, None, 0)

    assert run.sent_this_run is True
    mailbox_id, when = holds[0]
    assert mailbox_id == 1
    assert NOW + timedelta(seconds=180) <= when <= NOW + timedelta(seconds=900)


@pytest.fixture
def day_hold(monkeypatch):
    def build(used: int):
        holds: list[tuple[int, datetime]] = []

        async def sends_today(db, user_id):
            return used

        async def hold_until(mailbox_id, when):
            holds.append((mailbox_id, when))

        monkeypatch.setattr(email_contacting, "AsyncSessionLocal", _NoSession)
        monkeypatch.setattr(email_contacting, "datetime", _FrozenClock(NOW))
        monkeypatch.setattr(limits, "sends_today", sends_today)
        monkeypatch.setattr(pacing, "hold_until", hold_until)
        return holds

    return build


async def test_a_run_with_sending_left_in_the_day_is_not_held_back(day_hold):
    holds = day_hold(used=5)

    await email_contacting._hold_if_the_day_is_spent(USER, 1, 20)

    assert holds == []


async def test_a_mailbox_that_used_up_its_day_waits_for_the_next_one(day_hold):
    holds = day_hold(used=20)

    await email_contacting._hold_if_the_day_is_spent(USER, 1, 20)

    assert holds == [(1, datetime(2026, 11, 18, tzinfo=timezone.utc))]


@pytest.fixture
def full_run(monkeypatch):
    def build(next_send_at, blocker=None):
        worked: list[str] = []
        holds: list[tuple[int, datetime]] = []
        mailbox = SimpleNamespace(
            id=1,
            email="me@acme.test",
            status=MailboxStatus.ACTIVE,
            next_send_at=next_send_at,
            warmup_started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            provider="gmail",
        )

        async def get_settings(db, user_id):
            return _settings()

        async def get_for_user(db, user_id):
            return mailbox

        async def get_user_info(db, user_id):
            return SimpleNamespace(has_profile=True)

        async def default_template(db, user_id):
            return None

        async def get_email_send_schedule(db, user_id):
            return email_contacting.SEND_ANYTIME

        async def sweep(user_id, settings, now):
            return 0

        async def sends_today(db, user_id):
            return 0

        async def hold_until(mailbox_id, when):
            holds.append((mailbox_id, when))

        def step(name):
            async def run(self):
                worked.append(name)

            return run

        monkeypatch.setattr(email_contacting, "AsyncSessionLocal", _NoSession)
        monkeypatch.setattr(email_contacting, "datetime", _FrozenClock(NOW))
        monkeypatch.setattr(email_contacting, "get_settings", get_settings)
        monkeypatch.setattr(email_contacting.mailbox_manager, "get_for_user", get_for_user)
        monkeypatch.setattr(email_contacting, "get_user_info", get_user_info)
        monkeypatch.setattr(email_contacting, "default_template", default_template)
        monkeypatch.setattr(email_contacting, "get_email_send_schedule", get_email_send_schedule)
        monkeypatch.setattr(email_contacting, "writer_blocker", lambda *args: blocker)
        monkeypatch.setattr(email_contacting, "get_email_provider", lambda mailbox: object())
        monkeypatch.setattr(email_contacting.no_response_sweeper, "sweep", sweep)
        monkeypatch.setattr(email_contacting._OutreachRun, "first_touches", step("first_touches"))
        monkeypatch.setattr(email_contacting._OutreachRun, "follow_ups", step("follow_ups"))
        monkeypatch.setattr(limits, "sends_today", sends_today)
        monkeypatch.setattr(pacing, "hold_until", hold_until)
        return worked, holds

    return build


async def test_a_scheduled_run_stays_away_while_the_mailbox_is_between_sends(full_run):
    worked, holds = full_run(NOW + timedelta(minutes=5))

    await email_contacting._run(USER, True, _keep_going)

    assert worked == []
    assert holds == []


async def test_run_now_waits_out_the_gap_too(full_run):
    worked, _ = full_run(NOW + timedelta(minutes=5))

    await email_contacting._run(USER, False, _keep_going)

    assert worked == []


async def test_a_mailbox_that_has_never_sent_goes_straight_away(full_run):
    worked, _ = full_run(None)

    await email_contacting._run(USER, True, _keep_going)

    assert worked == ["first_touches", "follow_ups"]


async def test_a_user_who_cannot_send_yet_keeps_their_clock_untouched(full_run):
    worked, holds = full_run(None, blocker="Upload a résumé")

    await email_contacting._run(USER, True, _keep_going)

    assert worked == []
    assert holds == []


def test_the_outreach_tick_runs_often_enough_to_fill_the_gaps():
    job = next(job for job in scheduler.JOBS if job.name == "outreach_run")

    assert job.interval_seconds <= OutreachSettings(user_id=USER).min_gap_seconds
