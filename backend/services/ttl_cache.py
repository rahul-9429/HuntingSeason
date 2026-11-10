import asyncio
import time
from collections import OrderedDict
from typing import Awaitable, Callable, Generic, Hashable, Optional, TypeVar

V = TypeVar("V")


class TTLCache(Generic[V]):
    def __init__(self, ttl_seconds: float, max_entries: int):
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._entries: "OrderedDict[Hashable, tuple[V, float]]" = OrderedDict()
        self._in_flight: dict[Hashable, "asyncio.Future[V]"] = {}

    def get(self, key: Hashable) -> Optional[V]:
        entry = self._entries.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() >= expires_at:
            self._entries.pop(key, None)
            return None
        return value

    def set(self, key: Hashable, value: V) -> None:
        self._entries[key] = (value, time.monotonic() + self._ttl)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()
        self._in_flight.clear()

    async def get_or_load(
        self, key: Hashable, load: Callable[[], Awaitable[V]]
    ) -> tuple[V, bool]:
        cached = self.get(key)
        if cached is not None:
            return cached, False

        pending = self._in_flight.get(key)
        if pending is not None:
            return await asyncio.shield(pending), False

        future: "asyncio.Future[V]" = asyncio.get_running_loop().create_future()
        self._in_flight[key] = future
        try:
            value = await load()
        except asyncio.CancelledError:
            future.cancel()
            raise
        except Exception as exc:
            future.set_exception(exc)
            future.exception()
            raise
        finally:
            self._in_flight.pop(key, None)

        self.set(key, value)
        future.set_result(value)
        return value, True
