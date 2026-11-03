import hashlib
import logging
import os
from typing import Any, Optional

from openai import AsyncOpenAI

from services.errors import ServiceError

logger = logging.getLogger(__name__)


def _price(name: str) -> Optional[float]:
    value = os.getenv(name)
    return float(value) if value else None


_PRICE_INPUT_PER_MTOK = _price("OPENAI_PRICE_INPUT_PER_MTOK")
_PRICE_OUTPUT_PER_MTOK = _price("OPENAI_PRICE_OUTPUT_PER_MTOK")

_client: Optional[AsyncOpenAI] = None


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not os.getenv("OPENAI_API_KEY"):
            raise ServiceError("OPENAI_API_KEY is not set", status_code=500)
        _client = AsyncOpenAI(timeout=60, max_retries=1)
    return _client


def _cost_usd(input_tokens: int, output_tokens: int) -> Optional[float]:
    if _PRICE_INPUT_PER_MTOK is None or _PRICE_OUTPUT_PER_MTOK is None:
        return None
    return (
        input_tokens * _PRICE_INPUT_PER_MTOK + output_tokens * _PRICE_OUTPUT_PER_MTOK
    ) / 1_000_000


def safety_identifier(user_id: int) -> str:
    return hashlib.sha256(f"jobsearch-user-{user_id}".encode()).hexdigest()


def log_usage(purpose: str, model: str, usage: Any, user_id: int) -> None:
    fields = {"user_id": user_id, "purpose": purpose, "model": model}
    if usage is None:
        logger.info(
            "%s LLM call for user %s (%s): no usage reported", purpose, user_id, model, extra=fields
        )
        return
    cost = _cost_usd(usage.input_tokens, usage.output_tokens)
    logger.info(
        "%s LLM call for user %s (%s): %d input tokens (%d cached), %d output tokens (%d reasoning), cost %s",
        purpose,
        user_id,
        model,
        usage.input_tokens,
        usage.input_tokens_details.cached_tokens,
        usage.output_tokens,
        usage.output_tokens_details.reasoning_tokens,
        f"${cost:.6f}" if cost is not None else "unpriced",
        extra={
            **fields,
            "input_tokens": usage.input_tokens,
            "cached_tokens": usage.input_tokens_details.cached_tokens,
            "output_tokens": usage.output_tokens,
            "reasoning_tokens": usage.output_tokens_details.reasoning_tokens,
            "cost_usd": cost,
        },
    )
