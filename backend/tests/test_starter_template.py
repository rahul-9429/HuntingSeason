from types import SimpleNamespace

import pytest

from models.email_template import EmailTemplate
from models.enums import Writer
from models.outreach_settings import OutreachSettings
from services.email_event.openai_client import LLMError
from services.outreach import drafting, starter_template
from services.outreach import settings as email_settings
from services.outreach.user_info import UserInfo
from services.schemas.outreach import WrittenEmail

pytestmark = pytest.mark.anyio

GOOD_SUBJECT = "{role} at {company_name}"
GOOD_BODY = (
    "<p>Hi {contact_name},</p><p>I build payments systems, and I would like to be considered "
    "for {role} at {company_name}.</p><p>Would a 15-minute call work?</p>"
)

WITH_PROFILE = UserInfo(name="Ada", current_title="Backend Engineer", skills=("python",))
NO_PROFILE = UserInfo(name="Ada")


def email_settings_row(**fields) -> OutreachSettings:
    return OutreachSettings(user_id=1, **fields)


def email_template(**fields) -> EmailTemplate:
    base = dict(name="Mine", subject="s", body_html="<p>b</p>")
    return EmailTemplate(user_id=1, **{**base, **fields})



def test_new_settings_rows_default_to_the_ai_writer():
    assert email_settings_row().writer == Writer.EMAIL_AGENT


def test_templates_are_not_marked_generated_by_default():
    assert email_template().is_generated is False



def test_email_blocker_only_complains_about_the_writer_in_use():
    template_writer = email_settings_row(writer=Writer.TEMPLATE)
    ai_writer = email_settings_row(writer=Writer.EMAIL_AGENT)

    assert email_settings.writer_blocker(template_writer, None, WITH_PROFILE) is not None
    assert email_settings.writer_blocker(template_writer, email_template(), NO_PROFILE) is None
    assert email_settings.writer_blocker(ai_writer, None, WITH_PROFILE) is None
    assert email_settings.writer_blocker(ai_writer, None, NO_PROFILE) is not None



async def _record(sink, name):
    sink.append(name)
    return name


async def test_first_touch_falls_through_to_the_ai_writer(monkeypatch):
    called: list[str] = []
    monkeypatch.setattr(drafting, "_email_agent", lambda ctx, lead: _record(called, "email_agent"))
    monkeypatch.setattr(drafting, "_from_template", lambda ctx, lead: _record(called, "template"))

    ai_ctx = SimpleNamespace(settings=SimpleNamespace(writer=Writer.EMAIL_AGENT))
    await drafting.first_touch(ai_ctx, object())
    await drafting.first_touch(ai_ctx, object(), Writer.TEMPLATE)

    template_ctx = SimpleNamespace(settings=SimpleNamespace(writer=Writer.TEMPLATE))
    await drafting.first_touch(template_ctx, object())

    assert called == ["email_agent", "template", "template"]



class FakeSession:
    def __init__(self, scalars):
        self.scalars = list(scalars)
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.updates = 0

    async def scalar(self, statement):
        return self.scalars.pop(0)

    async def execute(self, statement):
        self.updates += 1
        return None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def fake_writer(monkeypatch, *, email=None, error=None):
    calls: list[str] = []

    async def generate_structured(*, system, user, schema, user_id, purpose, **kwargs):
        calls.append(purpose)
        if error is not None:
            raise error
        return email

    monkeypatch.setattr(starter_template.openai_client, "generate_structured", generate_structured)
    return calls


def good_email() -> WrittenEmail:
    return WrittenEmail(subject=GOOD_SUBJECT, body=GOOD_BODY)


def with_profile(monkeypatch, user_info=WITH_PROFILE):
    async def get_user_info(db, user_id):
        return user_info

    monkeypatch.setattr(starter_template, "get_user_info", get_user_info)


async def test_a_resume_seeds_one_default_email_template(monkeypatch):
    with_profile(monkeypatch)
    calls = fake_writer(monkeypatch, email=good_email())
    db = FakeSession([None, None])

    await starter_template.regenerate(db, 1)

    assert len(calls) == 1
    assert len(db.added) == 1
    (email,) = db.added
    assert isinstance(email, EmailTemplate)
    assert email.is_default and email.is_generated and email.skip_ai is False
    assert "{contact_name}" in email.body_html
    assert db.commits == 1


async def test_reparsing_overwrites_the_generated_template(monkeypatch):
    with_profile(monkeypatch)
    fake_writer(monkeypatch, email=good_email())
    existing_email = email_template(subject="old", body_html="<p>old</p>", is_generated=True)
    db = FakeSession([existing_email])

    await starter_template.regenerate(db, 1)

    assert db.added == []
    assert existing_email.subject == GOOD_SUBJECT
    assert "{company_name}" in existing_email.body_html


async def test_a_template_the_user_edited_is_left_alone(monkeypatch):
    with_profile(monkeypatch)
    calls = fake_writer(monkeypatch, email=good_email())
    db = FakeSession([None, email_template(is_default=True)])

    await starter_template.regenerate(db, 1)

    assert calls == []
    assert db.added == []


async def test_a_template_without_the_placeholders_is_discarded(monkeypatch):
    with_profile(monkeypatch)
    fake_writer(
        monkeypatch,
        email=WrittenEmail(subject=GOOD_SUBJECT, body="<p>Hi Dave, I want to join Acme.</p>"),
    )
    db = FakeSession([None, None])

    await starter_template.regenerate(db, 1)

    assert db.added == []
    assert db.rollbacks == 1


async def test_a_failed_ai_call_never_raises(monkeypatch):
    with_profile(monkeypatch)
    fake_writer(monkeypatch, error=LLMError("the model is down"))
    db = FakeSession([None, None])

    await starter_template.regenerate(db, 1)

    assert db.added == []
    assert db.rollbacks == 1


async def test_nothing_is_generated_without_a_profile(monkeypatch):
    with_profile(monkeypatch, NO_PROFILE)
    calls = fake_writer(monkeypatch, email=good_email())
    db = FakeSession([])

    await starter_template.regenerate(db, 1)

    assert calls == []
    assert db.added == []
