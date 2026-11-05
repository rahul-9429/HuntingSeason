from dotenv import load_dotenv

load_dotenv(override=True)

import asyncio
import json
import logging
import os
import signal
import time
from contextlib import suppress
from typing import cast

from db.session import async_engine
from services.email_providers import microsoft_provider
from services.json_logging import configure_logging
from services.redis import close_redis, get_redis
from services.redis._tasks import QUEUE_KEY, processing_key
from tasks import scheduler
from tasks.registry import CONCURRENCY, REGISTRY, TaskName

logger = logging.getLogger("tasks.worker")

WORKER_ID = os.getenv("WORKER_ID", "worker-1")
MAX_IN_FLIGHT = 10
POP_TIMEOUT_SECONDS = 2
SHUTDOWN_GRACE_SECONDS = 20


class Worker:
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.processing = processing_key(worker_id)
        self.slots = asyncio.Semaphore(MAX_IN_FLIGHT)
        self.task_slots = {
            name: asyncio.Semaphore(CONCURRENCY.get(name, 1)) for name in REGISTRY
        }
        self.running: set[asyncio.Task[None]] = set()

    async def requeue_unfinished(self) -> None:
        redis = get_redis()
        moved = 0
        while await redis.lmove(self.processing, QUEUE_KEY, "LEFT", "RIGHT") is not None:
            moved += 1
        if moved:
            logger.warning(
                "Re-queued %d unfinished tasks",
                moved,
                extra={"worker_id": self.worker_id, "count": moved},
            )

    async def consume(self) -> None:
        redis = get_redis()
        while True:
            await self.slots.acquire()
            try:
                raw = await redis.blmove(
                    QUEUE_KEY, self.processing, POP_TIMEOUT_SECONDS, "RIGHT", "LEFT"
                )
            except Exception:
                self.slots.release()
                logger.exception(
                    "Couldn't pop from the task queue", extra={"worker_id": self.worker_id}
                )
                await asyncio.sleep(1)
                continue
            if raw is None:
                self.slots.release()
                continue
            task = asyncio.create_task(self._run(cast(str, raw)))
            self.running.add(task)
            task.add_done_callback(self.running.discard)

    async def _run(self, raw: str) -> None:
        try:
            await self._dispatch(raw)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Task failed: %s", raw[:200], extra={"worker_id": self.worker_id})
        finally:
            self.slots.release()
        try:
            await get_redis().lrem(self.processing, 1, raw)
        except Exception:
            logger.exception(
                "Couldn't clear a finished task: %s", raw[:200], extra={"worker_id": self.worker_id}
            )

    async def _dispatch(self, raw: str) -> None:
        try:
            item = json.loads(raw)
            name = item["task"]
            payload = item.get("payload") or {}
        except (ValueError, TypeError, KeyError, AttributeError):
            logger.error("Dropping malformed task: %s", raw[:200], extra={"worker_id": self.worker_id})
            return
        if name not in REGISTRY:
            logger.warning(
                "Dropping unknown task %s", name, extra={"task": name, "worker_id": self.worker_id}
            )
            return

        task_name = cast(TaskName, name)
        async with self.task_slots[task_name]:
            started = time.monotonic()
            await REGISTRY[task_name](payload)
            logger.info(
                "Task %s finished in %.1fs",
                task_name,
                time.monotonic() - started,
                extra={"task": task_name, "worker_id": self.worker_id},
            )

    async def drain(self, timeout: float) -> None:
        if not self.running:
            return
        _, pending = await asyncio.wait(set(self.running), timeout=timeout)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


async def main() -> None:
    worker = Worker(WORKER_ID)
    await worker.requeue_unfinished()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)

    logger.info("Worker %s started", WORKER_ID, extra={"worker_id": WORKER_ID})
    consumer = asyncio.create_task(worker.consume())
    schedule = asyncio.create_task(scheduler.run_forever())
    try:
        await stop.wait()
    finally:
        logger.info("Worker %s stopping", WORKER_ID, extra={"worker_id": WORKER_ID})
        consumer.cancel()
        schedule.cancel()
        await asyncio.gather(consumer, schedule, return_exceptions=True)
        await worker.drain(SHUTDOWN_GRACE_SECONDS)
        await microsoft_provider.close_client()
        await close_redis()
        await async_engine.dispose()


if __name__ == "__main__":
    configure_logging()
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
