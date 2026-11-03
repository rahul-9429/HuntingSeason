from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services import resumes
from api.api_services.errors import ServiceError
from api.dependencies.authenticate import get_current_user_claims
from api.type_models.career_profile import MAX_RESUME_BYTES, ResumeOut
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db
from services import resume_parsing

router = APIRouter(
    prefix="/v1/resumes",
    tags=["resumes"],
)


@router.post("", response_model=ResumeOut, status_code=202)
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> ResumeOut:
    # One byte over the cap is enough to reject it without reading a huge file
    data = await file.read(MAX_RESUME_BYTES + 1)
    try:
        row = await resumes.upload(db, claims.user_id, file.filename or "", data)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    background_tasks.add_task(resume_parsing.parse, row.id)
    return resumes.to_out(row)


@router.get("/latest", response_model=Optional[ResumeOut])
async def get_latest_resume(
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> Optional[ResumeOut]:
    row = await resumes.latest(db, claims.user_id)
    return resumes.to_out(row) if row is not None else None


@router.get("/{resume_id}", response_model=ResumeOut)
async def get_resume(
    resume_id: int,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> ResumeOut:
    try:
        return resumes.to_out(await resumes.get(db, claims.user_id, resume_id))
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
