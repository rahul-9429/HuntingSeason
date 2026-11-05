from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services import mailbox
from api.api_services.errors import ServiceError
from api.dependencies.authenticate import get_current_user_claims
from api.type_models.mailbox import (
    AuthUrl,
    ConnectRequest,
    MailboxOut,
    SentEmailOut,
    TestSendRequest,
)
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db
from models.enums import MailboxProvider

router = APIRouter(
    prefix="/mailbox",
    tags=["mailbox"],
)


@router.get("/{provider}/auth-url", response_model=AuthUrl)
async def get_auth_url(
    provider: MailboxProvider,
    redirect_uri: str = Query(),
    claims: UserClaims = Depends(get_current_user_claims),
) -> AuthUrl:
    try:
        return AuthUrl(url=await mailbox.auth_url(claims.user_id, provider, redirect_uri))
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/connect", response_model=MailboxOut)
async def connect(
    req: ConnectRequest,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> MailboxOut:
    try:
        return await mailbox.connect(db, claims.user_id, req)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("", response_model=MailboxOut)
async def get_mailbox(
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> MailboxOut:
    try:
        return await mailbox.get(db, claims.user_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.delete("", status_code=204)
async def delete_mailbox(
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    await mailbox.delete(db, claims.user_id)
    return Response(status_code=204)


@router.post("/test-send", response_model=SentEmailOut)
async def test_send(
    req: TestSendRequest,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> SentEmailOut:
    try:
        sent = await mailbox.test_send(db, claims.user_id, req)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return SentEmailOut.model_validate(sent)
