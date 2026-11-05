from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services import threads
from api.api_services.errors import ServiceError
from api.dependencies.authenticate import get_current_user_claims
from api.type_models.threads import (
    InboxFilter,
    MessageOut,
    ReplyIn,
    ThreadList,
    ThreadOut,
    ThreadPatch,
)
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db

router = APIRouter(
    prefix="/v1/threads",
    tags=["threads"],
)

ThreadId = Annotated[int, Path(ge=1, le=2_147_483_647)]


@router.get("", response_model=ThreadList)
async def list_threads(
    inbox_filter: InboxFilter = Query(default="all", alias="filter"),
    q: str = Query(default="", max_length=200),
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> ThreadList:
    return await threads.list_threads(db, claims.user_id, inbox_filter, q)


@router.get("/{thread_id}", response_model=ThreadOut)
async def get_thread(
    thread_id: ThreadId,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> ThreadOut:
    try:
        return await threads.get(db, claims.user_id, thread_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.patch("/{thread_id}", response_model=ThreadOut)
async def update_thread(
    thread_id: ThreadId,
    patch: ThreadPatch,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> ThreadOut:
    try:
        return await threads.update(db, claims.user_id, thread_id, patch)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/{thread_id}/messages", response_model=MessageOut, status_code=201)
async def reply(
    thread_id: ThreadId,
    req: ReplyIn,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> MessageOut:
    try:
        return await threads.reply(db, claims.user_id, thread_id, req.body)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
