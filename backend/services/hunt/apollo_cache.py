import asyncio
import logging
from datetime import timedelta
from typing import Any, Optional, cast

from sqlalchemy import ColumnElement, CursorResult, and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import AsyncSessionLocal
from models.apollo_cache import ApolloCache

logger = logging.getLogger(__name__)

TTLS = {
    "page": timedelta(hours=24),
    "postings": timedelta(days=7),
    "people": timedelta(days=7),
    "hunter": timedelta(days=30),
    "tavily": timedelta(days=30),
}
CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60


def _ttl(key: str) -> timedelta:
    return TTLS[key.split(":", 1)[0]]


def _expired() -> ColumnElement[bool]:
    return or_(
        *(
            and_(ApolloCache.key.startswith(f"{kind}:"), ApolloCache.fetched_at <= func.now() - ttl)
            for kind, ttl in TTLS.items()
        )
    )


async def get(db: AsyncSession, key: str) -> Optional[Any]:
    return (
        await db.execute(
            select(ApolloCache.payload).where(
                ApolloCache.key == key, ApolloCache.fetched_at > func.now() - _ttl(key)
            )
        )
    ).scalar_one_or_none()


async def put(db: AsyncSession, key: str, payload: Any) -> None:
    insert = pg_insert(ApolloCache).values(key=key, payload=payload)
    try:
        await db.execute(
            insert.on_conflict_do_update(
                index_elements=["key"],
                set_={"payload": insert.excluded.payload, "fetched_at": func.now()},
            )
        )
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Couldn't store %s in the Apollo cache", key, extra={"cache_key": key})


async def delete_expired() -> int:
    async with AsyncSessionLocal() as db:
        result = cast(CursorResult[Any], await db.execute(delete(ApolloCache).where(_expired())))
        await db.commit()
        return result.rowcount


async def run_cleanup_forever() -> None:
    while True:
        try:
            removed = await delete_expired()
            logger.info(
                "Apollo cache cleanup removed %d expired rows", removed, extra={"rows_removed": removed}
            )
        except Exception:
            logger.exception("Apollo cache cleanup failed")
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
