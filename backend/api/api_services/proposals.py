from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services.errors import ServiceError
from api.type_models.proposals import ProposalOut, ProposalUpdate, ThreadMessageOut
from models.email_event import EmailEvent
from models.enums import ProposalStatus
from models.reply_proposal import ReplyProposal
from services.email_event import proposals as reply_sender
from services.email_event.threads import thread_events


async def _get(db: AsyncSession, user_id: int, proposal_id: int) -> ReplyProposal:
    proposal = await db.scalar(
        select(ReplyProposal).where(ReplyProposal.id == proposal_id, ReplyProposal.user_id == user_id)
    )
    if proposal is None:
        raise ServiceError("Draft not found", status_code=404)
    return proposal


def _require_pending(proposal: ReplyProposal) -> None:
    if proposal.status != ProposalStatus.PENDING:
        raise ServiceError(f"This draft is already {proposal.status.value}", status_code=409)


async def list_for(
    db: AsyncSession, user_id: int, status: Optional[ProposalStatus], limit: int, offset: int
) -> list[ProposalOut]:
    query = select(ReplyProposal).where(ReplyProposal.user_id == user_id)
    if status is not None:
        query = query.where(ReplyProposal.status == status)
    proposals = await db.scalars(
        query.order_by(ReplyProposal.created_at.desc(), ReplyProposal.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [ProposalOut.model_validate(proposal) for proposal in proposals]


async def get(db: AsyncSession, user_id: int, proposal_id: int) -> ProposalOut:
    return ProposalOut.model_validate(await _get(db, user_id, proposal_id))


async def thread(db: AsyncSession, user_id: int, proposal_id: int) -> list[ThreadMessageOut]:
    proposal = await _get(db, user_id, proposal_id)
    event = await db.get(EmailEvent, proposal.email_event_id)
    if event is None or event.mailbox_id is None:
        return []
    return [
        ThreadMessageOut.model_validate(message)
        for message in await thread_events(db, event.mailbox_id, event.thread_id)
    ]


async def _update_pending(
    db: AsyncSession, user_id: int, proposal_id: int, values: dict[str, Any]
) -> ProposalOut:
    proposal = await _get(db, user_id, proposal_id)
    _require_pending(proposal)
    updated = await db.scalar(
        sql_update(ReplyProposal)
        .where(
            ReplyProposal.id == proposal_id,
            ReplyProposal.user_id == user_id,
            ReplyProposal.status == ProposalStatus.PENDING,
        )
        .values(**values)
        .returning(ReplyProposal.id)
    )
    await db.commit()
    if updated is None:
        raise ServiceError("This draft was just sent or resolved", status_code=409)
    await db.refresh(proposal)
    return ProposalOut.model_validate(proposal)


async def update(
    db: AsyncSession, user_id: int, proposal_id: int, req: ProposalUpdate
) -> ProposalOut:
    changes = req.model_dump(exclude_unset=True, exclude_none=True)
    for field in ("cc", "bcc"):
        if field in changes:
            changes[field] = list(dict.fromkeys(str(address).lower() for address in changes[field]))
    if not changes:
        return await get(db, user_id, proposal_id)
    return await _update_pending(db, user_id, proposal_id, changes)


async def approve(user_id: int, proposal_id: int) -> ProposalOut:
    try:
        return ProposalOut.model_validate(await reply_sender.send(user_id, proposal_id))
    except reply_sender.ProposalError as exc:
        raise ServiceError(exc.detail, status_code=exc.status_code) from exc


async def reject(db: AsyncSession, user_id: int, proposal_id: int) -> ProposalOut:
    return await _update_pending(
        db,
        user_id,
        proposal_id,
        {"status": ProposalStatus.REJECTED, "resolved_at": datetime.now(timezone.utc)},
    )
