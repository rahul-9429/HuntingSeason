from datetime import datetime
from typing import Optional

from ._client import get_redis, key

BATCH_SECONDS = 30


async def claim_gmail_sync(mailbox_id: int) -> bool:
    return bool(
        await get_redis().set(key("gmail_sync_pending", mailbox_id), "1", nx=True, ex=BATCH_SECONDS)
    )


async def release_gmail_sync(mailbox_id: int) -> None:
    await get_redis().delete(key("gmail_sync_pending", mailbox_id))


async def add_outlook_pending(mailbox_id: int, message_ids: list[str]) -> None:
    if message_ids:
        await get_redis().sadd(key("outlook_pending", mailbox_id), *message_ids)


async def claim_outlook_sync(mailbox_id: int) -> bool:
    return bool(
        await get_redis().set(
            key("outlook_sync_scheduled", mailbox_id), "1", nx=True, ex=BATCH_SECONDS
        )
    )


async def release_outlook_sync(mailbox_id: int) -> None:
    await get_redis().delete(key("outlook_sync_scheduled", mailbox_id))


async def take_outlook_pending(mailbox_id: int) -> list[str]:
    redis = get_redis()
    pending = key("outlook_pending", mailbox_id)
    processing = key("outlook_processing", mailbox_id)
    async with redis.pipeline(transaction=True) as pipe:
        pipe.sunionstore(processing, [processing, pending])
        pipe.delete(pending)
        await pipe.execute()
    return sorted(str(message_id) for message_id in await redis.smembers(processing))


async def finish_outlook_pending(mailbox_id: int) -> None:
    await get_redis().delete(key("outlook_processing", mailbox_id))


async def last_outlook_safety_sync(mailbox_id: int) -> Optional[datetime]:
    value = await get_redis().get(key("outlook_safety_sync", mailbox_id))
    return datetime.fromisoformat(str(value)) if value else None


async def set_last_outlook_safety_sync(mailbox_id: int, at: datetime) -> None:
    await get_redis().set(key("outlook_safety_sync", mailbox_id), at.isoformat(), ex=7 * 86400)
