from datetime import datetime, timezone
from typing import Any

from sqlalchemy import update

from db.session import AsyncSessionLocal
from models.enums import ProposalStatus
from models.reply_proposal import ReplyProposal


async def handle(payload: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(ReplyProposal)
            .where(ReplyProposal.status == ProposalStatus.PENDING, ReplyProposal.expires_at < now)
            .values(status=ProposalStatus.EXPIRED, resolved_at=now)
        )
        await db.commit()
