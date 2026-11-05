from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services import proposals
from api.api_services.errors import ServiceError
from api.dependencies.authenticate import get_current_user_claims
from api.type_models.proposals import ProposalOut, ProposalUpdate, ThreadMessageOut
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db
from models.enums import ProposalStatus

router = APIRouter(
    prefix="/proposals",
    tags=["proposals"],
)


@router.get("", response_model=list[ProposalOut])
async def list_proposals(
    status: Optional[ProposalStatus] = Query(default=ProposalStatus.PENDING),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> list[ProposalOut]:
    return await proposals.list_for(db, claims.user_id, status, limit, offset)


@router.get("/{proposal_id}", response_model=ProposalOut)
async def get_proposal(
    proposal_id: int,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> ProposalOut:
    try:
        return await proposals.get(db, claims.user_id, proposal_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/{proposal_id}/thread", response_model=list[ThreadMessageOut])
async def get_thread(
    proposal_id: int,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> list[ThreadMessageOut]:
    try:
        return await proposals.thread(db, claims.user_id, proposal_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.patch("/{proposal_id}", response_model=ProposalOut)
async def update_proposal(
    proposal_id: int,
    req: ProposalUpdate,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> ProposalOut:
    try:
        return await proposals.update(db, claims.user_id, proposal_id, req)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/{proposal_id}/approve", response_model=ProposalOut)
async def approve_proposal(
    proposal_id: int,
    claims: UserClaims = Depends(get_current_user_claims),
) -> ProposalOut:
    try:
        return await proposals.approve(claims.user_id, proposal_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/{proposal_id}/reject", response_model=ProposalOut)
async def reject_proposal(
    proposal_id: int,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> ProposalOut:
    try:
        return await proposals.reject(db, claims.user_id, proposal_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
