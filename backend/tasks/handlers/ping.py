import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def handle(payload: dict[str, Any]) -> None:
    seconds = float(payload.get("sleep") or 0)
    if seconds > 0:
        await asyncio.sleep(seconds)
    logger.info("pong", extra={"payload": payload})
