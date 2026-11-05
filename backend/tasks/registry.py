from typing import Any, Awaitable, Callable, Literal

from tasks.handlers import (
    auto_hunt,
    classify_pending,
    gmail_sync,
    gmail_watch_renew,
    outlook_safety_sync,
    outlook_subscription_renew,
    outlook_sync,
    outreach_run,
    ping,
    proposal_auto_send,
    proposal_expire,
)

TaskName = Literal[
    "ping",
    "auto_hunt",
    "gmail_sync",
    "outlook_sync",
    "outlook_safety_sync",
    "gmail_watch_renew",
    "outlook_subscription_renew",
    "outreach_run",
    "proposal_auto_send",
    "proposal_expire",
    "classify_pending",
]
Handler = Callable[[dict[str, Any]], Awaitable[None]]

REGISTRY: dict[TaskName, Handler] = {
    "ping": ping.handle,
    "auto_hunt": auto_hunt.handle,
    "gmail_sync": gmail_sync.handle,
    "outlook_sync": outlook_sync.handle,
    "outlook_safety_sync": outlook_safety_sync.handle,
    "gmail_watch_renew": gmail_watch_renew.handle,
    "outlook_subscription_renew": outlook_subscription_renew.handle,
    "outreach_run": outreach_run.handle,
    "proposal_auto_send": proposal_auto_send.handle,
    "proposal_expire": proposal_expire.handle,
    "classify_pending": classify_pending.handle,
}

CONCURRENCY: dict[TaskName, int] = {
    "auto_hunt": 2,
    "gmail_sync": 4,
    "outlook_sync": 4,
    "outlook_safety_sync": 2,
    "outreach_run": 2,
}
