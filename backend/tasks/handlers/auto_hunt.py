from typing import Any

from services.hunt import auto_hunt


async def handle(payload: dict[str, Any]) -> None:
    await auto_hunt.run(
        int(payload["user_id"]), scheduled=bool(payload.get("scheduled", False))
    )
