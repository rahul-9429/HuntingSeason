import logging
import os

from services import openai_client
from services.errors import ServiceError
from services.schemas.contacts import ManagerTitles, WebPeople, WebPerson

logger = logging.getLogger(__name__)

CONTACT_MODEL = os.getenv("OPENAI_FILTER_MODEL", "gpt-5.6-luna")
MAX_OUTPUT_TOKENS = 4000

MANAGER_TITLES_PROMPT = """\
A job seeker wants one of these roles:
{roles}

List the job titles of the people who would hire for these roles: the
managers the roles report to, most likely first, at most 6. Write concrete
job titles as they appear on LinkedIn (e.g. "backend engineer" ->
"engineering manager", "head of engineering", "vp engineering", "cto";
"account executive" -> "sales manager", "head of sales", "vp sales").
Don't include recruiters or HR titles.
"""

WEB_PEOPLE_PROMPT = """\
Below are web search results about people at {company} ({domain}).

List the people who currently work at {company} with a job title like one of:
{titles}

Use only what the results say. For each person give their full name, their
current job title at {company}, and the url of the result they appear in,
copied exactly. Skip anyone who has left {company}, works somewhere else, or
whose title isn't stated. Return an empty list if nobody fits.

Results:
{results}
"""


class ContactLLMError(ServiceError):
    status_code = 502


async def hiring_manager_titles(roles: list[str], user_id: int) -> list[str]:
    prompt = MANAGER_TITLES_PROMPT.format(roles="\n".join(f"- {r}" for r in roles))
    try:
        response = await openai_client.client().responses.parse(
            model=CONTACT_MODEL,
            reasoning={"effort": "low"},
            input=prompt,
            text_format=ManagerTitles,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            store=False,
            safety_identifier=openai_client.safety_identifier(user_id),
        )
    except ServiceError:
        raise
    except Exception as exc:
        logger.exception("Hiring manager titles LLM call failed", extra={"user_id": user_id})
        raise ContactLLMError("Couldn't work out who hires for these roles") from exc

    openai_client.log_usage("Hiring manager titles", CONTACT_MODEL, response.usage, user_id)
    if response.output_parsed is None:
        raise ContactLLMError("Couldn't work out who hires for these roles")
    return response.output_parsed.titles


async def web_people(
    company: str, domain: str, titles: list[str], results: list[dict[str, str]], user_id: int
) -> list[WebPerson]:
    prompt = WEB_PEOPLE_PROMPT.format(
        company=company,
        domain=domain,
        titles="\n".join(f"- {t}" for t in titles),
        results="\n\n".join(
            f"[{i}] {r['title']}\n{r['url']}\n{r['content']}" for i, r in enumerate(results, 1)
        ),
    )
    try:
        response = await openai_client.client().responses.parse(
            model=CONTACT_MODEL,
            reasoning={"effort": "low"},
            input=prompt,
            text_format=WebPeople,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            store=False,
            safety_identifier=openai_client.safety_identifier(user_id),
        )
    except ServiceError:
        raise
    except Exception as exc:
        logger.exception("Web people LLM call failed", extra={"user_id": user_id})
        raise ContactLLMError("Couldn't read people from the web results") from exc

    openai_client.log_usage("Web people", CONTACT_MODEL, response.usage, user_id)
    if response.output_parsed is None:
        raise ContactLLMError("Couldn't read people from the web results")
    return response.output_parsed.people
