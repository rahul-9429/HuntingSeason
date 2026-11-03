import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, cast

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services.errors import ServiceError
from api.type_models.career_profile import MAX_RESUME_BYTES, ResumeOut, ResumeStatus
from models.resume import Resume
from services import s3
from services.schemas.career_profile import CareerProfile

logger = logging.getLogger(__name__)

PDF = "application/pdf"
UPLOADS_PER_DAY = int(os.getenv("RESUME_UPLOADS_PER_DAY", "10"))
# A row still "parsing" after this long lost its background task (restart, crash)
STALE_PARSE = timedelta(minutes=5)


class ResumeError(ServiceError):
    status_code = 400


class ResumeNotFound(ServiceError):
    status_code = 404


def to_out(row: Resume) -> ResumeOut:
    status, error = row.status, row.error
    if status == "parsing" and row.created_at < datetime.now(timezone.utc) - STALE_PARSE:
        status, error = "failed", "Reading the résumé took too long, upload it again"
    profile = None
    if row.extracted is not None:
        try:
            profile = CareerProfile.model_validate(row.extracted)
        except ValidationError:
            pass
    return ResumeOut(
        id=row.id,
        file_name=row.file_name,
        status=cast(ResumeStatus, status),
        error=error,
        created_at=row.created_at,
        parsed_at=row.parsed_at,
        profile=profile,
    )


async def uploads_today(db: AsyncSession, user_id: int) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(Resume)
            .where(Resume.user_id == user_id, Resume.created_at > func.now() - timedelta(days=1))
        )
    ).scalar_one()


async def _check_daily_cap(db: AsyncSession, user_id: int) -> None:
    if await uploads_today(db, user_id) >= UPLOADS_PER_DAY:
        raise ResumeError(
            f"You can upload {UPLOADS_PER_DAY} résumés a day, try again tomorrow", status_code=429
        )


def _check_pdf(file_name: str, data: bytes) -> None:
    if not file_name.lower().endswith(".pdf") or not data.startswith(b"%PDF-"):
        raise ResumeError("Upload your résumé as a PDF")
    if len(data) > MAX_RESUME_BYTES:
        raise ResumeError("The résumé must be 5 MB or smaller", status_code=413)


async def upload(db: AsyncSession, user_id: int, file_name: str, data: bytes) -> Resume:
    """Stores the PDF in S3 and adds a "parsing" row; the caller schedules resume_parsing.parse()."""
    file_name = " ".join(file_name.split())[:255] or "resume.pdf"
    _check_pdf(file_name, data)
    await _check_daily_cap(db, user_id)

    key = f"resumes/{user_id}/{uuid.uuid4().hex}.pdf"
    await s3.put(key, data, PDF)

    row = Resume(user_id=user_id, s3_key=key, file_name=file_name)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info("User %s uploaded résumé %s (%d bytes)", user_id, row.id, len(data))
    return row


async def latest(db: AsyncSession, user_id: int) -> Optional[Resume]:
    return (
        await db.execute(
            select(Resume).where(Resume.user_id == user_id).order_by(Resume.id.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def get(db: AsyncSession, user_id: int, resume_id: int) -> Resume:
    row: Optional[Resume] = (
        await db.execute(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id))
    ).scalar_one_or_none()
    if row is None:
        raise ResumeNotFound("Résumé not found")
    return row
