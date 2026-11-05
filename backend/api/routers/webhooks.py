import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services import webhooks
from db.get_db_session import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
)


async def _json(request: Request) -> Any:
    try:
        return json.loads(await request.body() or b"null")
    except ValueError:
        return None


@router.post("/gmail", status_code=204)
async def gmail(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    await webhooks.gmail_push(db, await _json(request))
    return Response(status_code=204)


@router.post("/outlook", status_code=202, response_model=None)
async def outlook(
    request: Request,
    validation_token: Optional[str] = Query(default=None, alias="validationToken"),
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    if validation_token is not None:
        return PlainTextResponse(validation_token, status_code=200)
    await webhooks.outlook_notifications(db, await _json(request))
    return Response(status_code=202)
