from typing import Any

from services.outreach import email_contacting


async def handle(payload: dict[str, Any]) -> None:
    await email_contacting.run(
        int(payload["user_id"]), scheduled=bool(payload.get("scheduled", False))
    )
