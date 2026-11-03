from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services import company_search
from api.api_services.errors import ServiceError
from api.dependencies.authenticate import get_current_user_claims
from api.type_models.company_search import (
    CompanySearchRequest,
    CompanySearchResponse,
    JobPostingsResponse,
)
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db

router = APIRouter(
    prefix="/v1/companies",
    tags=["companies"],
)


@router.post("/search", response_model=CompanySearchResponse)
async def search_companies(
    req: CompanySearchRequest,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> CompanySearchResponse:
    try:
        return await company_search.search(req, claims.user_id, db)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/{org_id}/job-postings", response_model=JobPostingsResponse)
async def get_job_postings(
    org_id: str = Path(pattern=r"^[0-9a-f]{24}$"),
    role: list[str] = Query(default=[]),
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> JobPostingsResponse:
    try:
        return await company_search.job_postings(org_id, role, claims.user_id, db)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
