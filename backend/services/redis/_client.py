import os
from typing import Optional

from redis.asyncio import Redis

ENV_PREFIX = "prod" if os.getenv("ENV") == "production" else "dev"

_client: Optional[Redis] = None


def key(*parts: object) -> str:
    return ":".join([ENV_PREFIX, *(str(part) for part in parts)])


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(
            os.getenv("REDIS_URL") or "redis://localhost:6379/0", decode_responses=True
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
