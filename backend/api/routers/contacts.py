from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services import contacts
from api.api_services.errors import ServiceError
from api.dependencies.authenticate import get_current_user_claims
from api.type_models.contacts import (
    ContactList,
    ContactType,
    Credits,
    OutreachRequest,
    RevealResponse,
)
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db

router = APIRouter(
    prefix="/v1",
    tags=["contacts"],
)


@router.get("/contacts", response_model=ContactList)
async def list_contacts(
    contact_type: Optional[ContactType] = Query(default=None, alias="type"),
    limit: int = Query(default=contacts.PAGE_SIZE, ge=1, le=contacts.MAX_PAGE_SIZE),
    cursor: Optional[str] = Query(default=None, max_length=256),
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> ContactList:
    try:
        return await contacts.list_contacts(db, claims.user_id, contact_type, limit, cursor)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/contacts/{contact_id}/reveal", response_model=RevealResponse)
async def reveal_contact(
    contact_id: int,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> RevealResponse:
    try:
        return await contacts.reveal(db, claims.user_id, contact_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/contacts/{contact_id}/outreach", response_model=RevealResponse)
async def send_outreach(
    contact_id: int,
    req: OutreachRequest,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> RevealResponse:
    try:
        return await contacts.send_outreach(db, claims.user_id, contact_id, req)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/credits", response_model=Credits)
async def get_credits(
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> Credits:
    return await contacts.credits(db, claims.user_id)
