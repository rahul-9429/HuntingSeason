import secrets
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from ._client import get_redis

_RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
end
return 0
"""


_EXTEND_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("EXPIRE", KEYS[1], ARGV[2])
end
return 0
"""


async def acquire(key: str, ttl: int) -> Optional[str]:
    token = secrets.token_hex(16)
    acquired = await get_redis().set(key, token, nx=True, ex=ttl)
    return token if acquired else None


async def release(key: str, token: str) -> None:
    await get_redis().eval(_RELEASE_SCRIPT, 1, key, token)


async def extend(key: str, token: str, ttl: int) -> bool:
    return bool(await get_redis().eval(_EXTEND_SCRIPT, 1, key, token, ttl))


@asynccontextmanager
async def lock(key: str, ttl: int) -> AsyncIterator[bool]:
    token = await acquire(key, ttl)
    try:
        yield token is not None
    finally:
        if token is not None:
            await release(key, token)
