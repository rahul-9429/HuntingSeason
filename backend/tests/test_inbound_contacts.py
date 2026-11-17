from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Optional

import pytest

from models.enums import Direction, MailboxProvider
from services.email_event import email_processor
from services.email_event.email_processor import EmailEventProcessor
from services.email_event.types import NormalizedEmailMessage

pytestmark = pytest.mark.anyio

USER = 1
NOW = datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)


def _message(
    direction: Direction = Direction.INBOUND, headers: Optional[dict] = None
) -> NormalizedEmailMessage:
    return NormalizedEmailMessage(
        provider=MailboxProvider.GMAIL,
        provider_message_id="m1",
        internet_message_id="<m1@acme.test>",
        thread_id="t1",
        direction=direction,
        from_address="Dana Scott <dana@acme.test>",
        to_addresses=["me@mine.test"],
        cc_addresses=[],
        subject="Are you available?",
        snippet="Are you available",
        body_html="<p>Are you available?</p>",
        sent_at=NOW,
        headers=headers or {},
    )


def _mailbox() -> SimpleNamespace:
    return SimpleNamespace(id=5, user_id=USER, email="me@mine.test")


class _FakeSession:
    def __init__(
        self,
        anchor: Optional[SimpleNamespace],
        thread_contact: Optional[int],
        sender_contact: Optional[int],
    ):
        self.anchor = anchor
        self.thread_contact = thread_contact
        self.sender_contact = sender_contact
        self.asked: list[str] = []
        self.inserted: Optional[dict] = None
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def scalar(self, statement):
        if type(statement).__name__ == "Insert":
            self.inserted = dict(statement.compile().params)
            return 77
        column = statement.column_descriptions[0]["name"]
        self.asked.append(column)
        if column == "SentEmail":
            return self.anchor
        if column == "user_contact_id":
            return self.thread_contact
        return self.sender_contact

    async def execute(self, statement):
        return None

    async def commit(self):
        self.commits += 1


@pytest.fixture
def process(monkeypatch):
    def build(anchor=None, thread_contact=None, sender_contact=None):
        db = _FakeSession(anchor, thread_contact, sender_contact)
        transitions: list[Optional[int]] = []
        classified: list[int] = []

        async def expire(db_, mailbox_id, thread_id, now):
            return None

        async def apply_sync_transition(db_, *, user_contact_id, **kwargs):
            transitions.append(user_contact_id)

        async def classify(event_id):
            classified.append(event_id)

        monkeypatch.setattr(email_processor, "AsyncSessionLocal", lambda: db)
        monkeypatch.setattr(email_processor.proposal_worker, "expire_thread_proposals", expire)
        monkeypatch.setattr(email_processor, "apply_sync_transition", apply_sync_transition)
        monkeypatch.setattr(email_processor.classification_worker, "classify", classify)
        return db, transitions, classified

    return build


async def test_a_known_contact_writing_in_a_new_thread_is_kept(process):
    db, transitions, classified = process(sender_contact=42)

    kept = await EmailEventProcessor()._process_one(_mailbox(), _message())

    assert kept is True
    assert db.inserted["user_contact_id"] == 42
    assert db.inserted["sent_email_id"] is None
    assert transitions == [42]
    assert classified == [77]


async def test_a_stranger_writing_in_a_new_thread_is_still_dropped(process):
    db, transitions, classified = process()

    kept = await EmailEventProcessor()._process_one(_mailbox(), _message())

    assert kept is False
    assert db.inserted is None
    assert transitions == []
    assert classified == []


async def test_an_outbound_message_with_nothing_to_anchor_it_is_dropped(process):
    db, _, _ = process(sender_contact=42)

    kept = await EmailEventProcessor()._process_one(
        _mailbox(), _message(Direction.OUTBOUND)
    )

    assert kept is False
    assert db.inserted is None


async def test_a_thread_we_already_matched_keeps_its_contact(process):
    db, transitions, _ = process(thread_contact=7, sender_contact=42)

    await EmailEventProcessor()._process_one(_mailbox(), _message())

    assert db.inserted["user_contact_id"] == 7
    assert transitions == [7]


async def test_the_sent_email_that_started_a_thread_still_wins(process):
    anchor = SimpleNamespace(id=3, user_contact_id=9)
    db, transitions, _ = process(anchor=anchor, thread_contact=7, sender_contact=42)

    await EmailEventProcessor()._process_one(_mailbox(), _message())

    assert db.inserted["user_contact_id"] == 9
    assert db.inserted["sent_email_id"] == 3
    assert db.asked == ["SentEmail"]


async def test_an_out_of_office_in_a_new_thread_is_not_adopted(process):
    db, _, _ = process(sender_contact=42)

    kept = await EmailEventProcessor()._process_one(
        _mailbox(), _message(headers={"auto-submitted": "auto-replied"})
    )

    assert kept is False
    assert db.inserted is None


async def test_a_bounce_in_a_new_thread_is_not_adopted(process, monkeypatch):
    db, _, _ = process(sender_contact=42)
    message = _message()
    bounce = NormalizedEmailMessage(
        **{**message.__dict__, "from_address": "mailer-daemon@acme.test"}
    )

    kept = await EmailEventProcessor()._process_one(_mailbox(), bounce)

    assert kept is False
    assert db.inserted is None


class _CaptureSession:
    def __init__(self, result=None):
        self.result = result
        self.params: Optional[dict] = None

    async def scalar(self, statement):
        self.params = dict(statement.compile().params)
        return self.result


async def test_the_display_name_and_the_casing_are_dropped_before_matching():
    db = _CaptureSession(result=42)

    found = await email_processor._contact_who_wrote(db, USER, "Dana Scott <DANA@Acme.test>")

    assert found == 42
    assert "dana@acme.test" in db.params.values()


@pytest.mark.parametrize("from_address", ["", "   ", "Nobody <>"])
async def test_an_email_with_no_address_to_read_matches_nobody(from_address):
    db = _CaptureSession(result=42)

    assert await email_processor._contact_who_wrote(db, USER, from_address) is None
    assert db.params is None


async def test_an_outbound_reply_sent_from_the_users_own_client_joins_the_thread(process):
    db, transitions, classified = process(thread_contact=7)

    kept = await EmailEventProcessor()._process_one(
        _mailbox(), _message(Direction.OUTBOUND)
    )

    assert kept is True
    assert db.inserted["user_contact_id"] == 7
    assert classified == []
