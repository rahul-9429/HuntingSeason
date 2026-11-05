import logging
import os
from typing import TypeVar

from pydantic import BaseModel

from services import openai_client as shared

logger = logging.getLogger(__name__)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
DEFAULT_MAX_OUTPUT_TOKENS = 4000

Parsed = TypeVar("Parsed", bound=BaseModel)


class LLMError(Exception):
    pass


async def generate_text(
    *,
    system: str,
    user: str,
    user_id: int,
    purpose: str,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
) -> str:
    try:
        response = await shared.client().responses.create(
            model=OPENAI_MODEL,
            reasoning={"effort": "low"},
            instructions=system,
            input=user,
            max_output_tokens=max_output_tokens,
            store=False,
            safety_identifier=shared.safety_identifier(user_id),
        )
    except Exception as exc:
        logger.warning("%s LLM call failed: %s", purpose, exc, extra={"user_id": user_id})
        raise LLMError(f"{purpose} call failed") from exc
    shared.log_usage(purpose, OPENAI_MODEL, response.usage, user_id)
    if response.status == "incomplete":
        raise LLMError(f"{purpose} call ran out of tokens")
    text = (response.output_text or "").strip()
    if not text:
        raise LLMError(f"{purpose} call returned nothing (status {response.status})")
    return text


async def generate_structured(
    *,
    system: str,
    user: str,
    schema: type[Parsed],
    user_id: int,
    purpose: str,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
) -> Parsed:
    try:
        response = await shared.client().responses.parse(
            model=OPENAI_MODEL,
            reasoning={"effort": "low"},
            instructions=system,
            input=user,
            text_format=schema,
            max_output_tokens=max_output_tokens,
            store=False,
            safety_identifier=shared.safety_identifier(user_id),
        )
    except Exception as exc:
        logger.warning("%s LLM call failed: %s", purpose, exc, extra={"user_id": user_id})
        raise LLMError(f"{purpose} call failed") from exc
    shared.log_usage(purpose, OPENAI_MODEL, response.usage, user_id)
    if response.status == "incomplete" or response.output_parsed is None:
        raise LLMError(f"{purpose} call returned nothing usable (status {response.status})")
    return response.output_parsed
