import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from api.api_services import clerk_webhook
from db.get_db_session import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clerk_webhook",
    tags=["clerk_webhook"],
)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def handle_clerk_webhook(request: Request, db: AsyncSession = Depends(get_async_db)):
    """
    Handles incoming webhooks from Clerk, verifies them, and calls the appropriate service.
    """
    svix_secret = os.environ.get("CLERK_WEBHOOK_SECRET")
    if not svix_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured.",
        )

    payload = await request.body()
    try:
        Webhook(svix_secret).verify(payload, dict(request.headers))
    # A signature that isn't valid base64 raises binascii.Error (a ValueError)
    # instead of WebhookVerificationError.
    except (WebhookVerificationError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature."
        )

    # svix 2.x's verify() only checks the signature and returns None, so the
    # event is parsed from the body it just verified.
    event = json.loads(payload)
    if not isinstance(event, dict):
        logger.warning("Received webhook with non-dict payload: %r", event)
        return Response(status_code=status.HTTP_202_ACCEPTED, content="Webhook received")

    event_type = event.get("type")
    data: dict[str, Any] = event.get("data") or {}

    if event_type == "user.created":
        await clerk_webhook.handle_user_created(db=db, event_data=data)
    else:
        logger.info(
            "Received unhandled Clerk event type '%s'", event_type, extra={"event_type": event_type}
        )

    return Response(status_code=status.HTTP_202_ACCEPTED, content="Webhook received")
