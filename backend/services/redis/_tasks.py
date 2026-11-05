import json
from typing import Any

from ._client import get_redis, key

QUEUE_KEY = key("tasks", "queue")


def processing_key(worker_id: str) -> str:
    return key("tasks", "processing", worker_id)


async def push_task(name: str, payload: dict[str, Any]) -> None:
    await get_redis().lpush(QUEUE_KEY, json.dumps({"task": name, "payload": payload}))
