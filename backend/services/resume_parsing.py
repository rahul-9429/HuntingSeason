import asyncio
import logging
from typing import Optional

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import AsyncSessionLocal
from models.resume import Resume
from services import career_profiles, resume_extraction, s3, user_profiles
from services.outreach import starter_template
from services.errors import ServiceError
from services.schemas.user_profile import ResumeDetails

logger = logging.getLogger(__name__)


async def _details(pdf: bytes, file_name: str, user_id: int) -> Optional[ResumeDetails]:
    try:
        return await resume_extraction.extract_details(pdf, file_name, user_id)
    except Exception:
        logger.exception("Couldn't read the profile details from a résumé", extra={"user_id": user_id})
        return None


async def _finish(db: AsyncSession, resume_id: int, **values) -> None:
    await db.execute(update(Resume).where(Resume.id == resume_id).values(**values))
    await db.commit()


async def parse_row(db: AsyncSession, row: Resume) -> None:
    resume_id, user_id = row.id, row.user_id
    try:
        pdf = await s3.get_bytes(row.s3_key)
        profile, details = await asyncio.gather(
            resume_extraction.extract_profile(pdf, row.file_name, user_id),
            _details(pdf, row.file_name, user_id),
        )
        await career_profiles.upsert(db, user_id, profile, source_resume_id=resume_id)
        if details is not None:
            await user_profiles.apply_resume(db, user_id, details)
    except Exception as exc:
        await db.rollback()
        if isinstance(exc, ServiceError):
            error = exc.detail
        else:
            logger.exception("Parsing résumé %s failed", resume_id)
            error = "Couldn't read that résumé, try again"
        await _finish(db, resume_id, status="failed", error=error)
        return

    await _finish(
        db,
        resume_id,
        status="parsed",
        extracted=profile.model_dump(),
        parsed_at=func.now(),
    )
    logger.info("Parsed résumé %s for user %s", resume_id, user_id)
    await starter_template.regenerate(db, user_id)


async def parse(resume_id: int) -> None:
    """Runs after the upload response (or in a worker), with its own session."""
    async with AsyncSessionLocal() as db:
        row = await db.get(Resume, resume_id)
        if row is not None:
            await parse_row(db, row)
