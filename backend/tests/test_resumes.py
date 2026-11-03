from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from openai.lib._pydantic import to_strict_json_schema

from api.api_services import resumes
from services.hunt import filters as company_filters
from api.api_services.errors import ServiceError
from api.dependencies.authenticate import get_current_user_claims
from api.main import app
from api.type_models.career_profile import MAX_RESUME_BYTES
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db
from models.resume import Resume
from services import openai_client, resume_extraction, resume_parsing, s3
from services.schemas.career_profile import CareerProfile
from services.schemas.common import MAX_ITEMS
from tests.conftest import make_profile

pytestmark = pytest.mark.anyio

USER = 7
KEY = f"resumes/{USER}/{'a' * 32}.pdf"
PROFILE = make_profile(current_title="Backend Engineer", seniority="senior", function="engineering")


PDF_BYTES = b"%PDF-1.7 fake"


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, row):
        row.id = len(self.added) + 1
        row.created_at = datetime.now(timezone.utc)
        self.added.append(row)

    async def commit(self):
        pass

    async def refresh(self, row):
        pass


@pytest.fixture
def uploads(monkeypatch):
    state = SimpleNamespace(today=0, stored={})

    async def uploads_today(db, user_id):
        return state.today

    async def put(key, data, content_type):
        state.stored[key] = (data, content_type)

    monkeypatch.setattr(resumes, "uploads_today", uploads_today)
    monkeypatch.setattr(s3, "put", put)
    return state


async def test_upload_stores_the_pdf_in_the_users_folder(uploads):
    db = FakeSession()
    row = await resumes.upload(db, USER, "  My  CV.pdf ", PDF_BYTES)

    (key,) = uploads.stored
    assert key.startswith(f"resumes/{USER}/") and key.endswith(".pdf")
    assert uploads.stored[key] == (PDF_BYTES, "application/pdf")
    assert row.s3_key == key and row.file_name == "My CV.pdf" and row.status == "parsing"
    assert db.added == [row]


@pytest.mark.parametrize(
    "file_name, data, status",
    [
        ("cv.docx", PDF_BYTES, 400),
        ("cv.pdf", b"PK\x03\x04 not a pdf", 400),
        ("cv.pdf", b"%PDF-" + b"x" * MAX_RESUME_BYTES, 413),
    ],
)
async def test_upload_rejects_bad_files(uploads, file_name, data, status):
    with pytest.raises(ServiceError) as exc:
        await resumes.upload(FakeSession(), USER, file_name, data)

    assert exc.value.status_code == status
    assert uploads.stored == {}


async def test_upload_daily_cap(uploads):
    uploads.today = resumes.UPLOADS_PER_DAY

    with pytest.raises(ServiceError) as exc:
        await resumes.upload(FakeSession(), USER, "cv.pdf", PDF_BYTES)

    assert exc.value.status_code == 429
    assert uploads.stored == {}


class FakeDb:
    def __init__(self):
        self.rollbacks = 0

    async def rollback(self):
        self.rollbacks += 1


def resume_row(**fields) -> Resume:
    row = Resume(user_id=USER, s3_key=KEY, file_name="cv.pdf", status="parsing")
    row.id = 3
    row.created_at = datetime.now(timezone.utc)
    for name, value in fields.items():
        setattr(row, name, value)
    return row


@pytest.fixture
def finished(monkeypatch):
    writes = []

    async def finish(db, resume_id, **values):
        writes.append((resume_id, values))

    async def get_bytes(key):
        assert key == KEY
        return b"%PDF-1.7"

    monkeypatch.setattr(resume_parsing, "_finish", finish)
    monkeypatch.setattr(s3, "get_bytes", get_bytes)
    return writes


async def test_parse_saves_the_profile(monkeypatch, finished, profiles):
    async def extract_profile(pdf, file_name, user_id):
        return PROFILE

    monkeypatch.setattr(resume_extraction, "extract_profile", extract_profile)
    await resume_parsing.parse_row(FakeDb(), resume_row())

    ((resume_id, values),) = finished
    assert resume_id == 3 and values["status"] == "parsed"
    assert values["extracted"] == PROFILE.model_dump()
    assert profiles.data[USER] == PROFILE


@pytest.mark.parametrize(
    "error, detail",
    [
        (resume_extraction.ResumeExtractionError("Couldn't find any career details"), "Couldn't find any career details"),
        (RuntimeError("boom"), "Couldn't read that résumé, try again"),
    ],
)
async def test_parse_failure_marks_the_resume_failed(monkeypatch, finished, profiles, error, detail):
    async def extract_profile(pdf, file_name, user_id):
        raise error

    monkeypatch.setattr(resume_extraction, "extract_profile", extract_profile)
    db = FakeDb()
    await resume_parsing.parse_row(db, resume_row())

    assert finished == [(3, {"status": "failed", "error": detail})]
    assert db.rollbacks == 1 and profiles.data == {}


def test_a_resume_stuck_parsing_reads_as_failed():
    stale = resumes.to_out(resume_row(created_at=datetime.now(timezone.utc) - timedelta(minutes=10)))
    fresh = resumes.to_out(resume_row())
    parsed = resumes.to_out(resume_row(status="parsed", extracted=PROFILE.model_dump()))

    assert stale.status == "failed" and stale.error
    assert fresh.status == "parsing" and fresh.profile is None
    assert parsed.profile == PROFILE


class FakeResponses:
    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.parsed, usage=None)


def use_openai(monkeypatch, parsed) -> FakeResponses:
    fake = FakeResponses(parsed)
    monkeypatch.setattr(openai_client, "client", lambda: SimpleNamespace(responses=fake))
    return fake


def extraction(profile: CareerProfile, employers=(), years=None) -> resume_extraction.ResumeExtraction:
    return resume_extraction.ResumeExtraction(
        years_of_experience=years,
        employers=list(employers),
        **profile.model_dump(exclude={"company_size_history"}),
    )


async def test_extraction_sends_the_pdf_as_a_file(monkeypatch):
    fake = use_openai(monkeypatch, extraction(PROFILE, years=6))

    assert await resume_extraction.extract_profile(b"%PDF", "cv.pdf", USER) == PROFILE
    (call,) = fake.calls
    file_part, prompt = call["input"][0]["content"]
    assert file_part["type"] == "input_file" and file_part["file_data"].startswith("data:application/pdf;base64,")
    assert call["text_format"] is resume_extraction.ResumeExtraction and call["store"] is False
    assert date.today().isoformat() in prompt["text"]


async def test_extraction_buckets_each_employers_headcount(monkeypatch):
    employers = [
        resume_extraction.Employer(name="Seed startup", employees=8),
        resume_extraction.Employer(name="Scale-up", employees=180),
        resume_extraction.Employer(name="Unknown agency", employees=None),
        resume_extraction.Employer(name="Another startup", employees=10),
        resume_extraction.Employer(name="Big tech", employees=150_000),
    ]
    use_openai(monkeypatch, extraction(PROFILE, employers))

    profile = await resume_extraction.extract_profile(b"%PDF", "cv.pdf", USER)
    assert profile.company_size_history == ["1,10", "51,200", "5001,10000"]


@pytest.mark.parametrize(
    "employees, bucket",
    [(None, None), (0, None), (1, "1,10"), (11, "11,50"), (1000, "501,1000"), (1001, "1001,5000"), (20_000, "5001,10000")],
)
def test_size_bucket(employees, bucket):
    assert resume_extraction.size_bucket(employees) == bucket


async def test_extraction_rejects_an_empty_profile(monkeypatch):
    use_openai(monkeypatch, extraction(make_profile()))

    with pytest.raises(resume_extraction.ResumeExtractionError):
        await resume_extraction.extract_profile(b"%PDF", "cv.pdf", USER)


async def test_filter_prompt_carries_the_profile_only_when_given(monkeypatch):
    fake = use_openai(monkeypatch, None)
    for profile in (None, PROFILE):
        with pytest.raises(company_filters.FilterGenerationError):
            await company_filters.generate_filters("", USER, profile)

    without, with_profile = (call["input"] for call in fake.calls)
    assert "extracted from their résumé" not in without and "Backend Engineer" not in without
    assert "Backend Engineer" in with_profile and company_filters.NO_DESCRIPTION in with_profile


def test_profile_strict_schema_and_cleanup():
    schema = to_strict_json_schema(CareerProfile)
    extraction_schema = to_strict_json_schema(resume_extraction.ResumeExtraction)
    profile = make_profile(
        current_title="  Senior   Engineer ",
        top_skills=["Python", "python", ""] + [f"skill {i}" for i in range(20)],
        company_size_history=["11,50", "11,50"],
        open_to_locations=["Remote", "India", "Dubai"],
    )

    assert set(schema["required"]) == set(schema["properties"])
    assert list(extraction_schema["properties"])[:3] == ["years_of_experience", "employers", "current_title"]
    assert profile.current_title == "Senior Engineer"
    assert profile.top_skills[0] == "Python" and len(profile.top_skills) == MAX_ITEMS
    assert profile.company_size_history == ["11,50"]
    assert profile.open_to_locations == ["India", "Dubai"]


def test_routes(monkeypatch, uploads, profiles):
    parsed = []

    async def parse(resume_id):
        parsed.append(resume_id)

    async def fake_db():
        yield FakeSession()

    monkeypatch.setattr(resume_parsing, "parse", parse)
    app.dependency_overrides[get_current_user_claims] = lambda: UserClaims(
        user_id=USER, user_email="user@example.com"
    )
    app.dependency_overrides[get_async_db] = fake_db
    try:
        with TestClient(app) as client:
            ok = client.post("/v1/resumes", files={"file": ("cv.pdf", PDF_BYTES, "application/pdf")})
            bad = client.post("/v1/resumes", files={"file": ("cv.doc", b"doc", "application/msword")})
            empty = client.get("/v1/career-profile")
            saved = client.put("/v1/career-profile", json=PROFILE.model_dump())
            invalid = client.put("/v1/career-profile", json={**PROFILE.model_dump(), "seniority": "mid"})
    finally:
        app.dependency_overrides.clear()

    assert ok.status_code == 202 and ok.json()["status"] == "parsing"
    assert parsed == [ok.json()["id"]]
    assert bad.status_code == 400
    assert empty.status_code == 200 and empty.json() is None
    assert saved.status_code == 200 and profiles.data[USER] == PROFILE
    assert invalid.status_code == 422
