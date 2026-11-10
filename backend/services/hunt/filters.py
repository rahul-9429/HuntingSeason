import logging
import os
from datetime import date
from typing import Optional

from services import openai_client
from services.errors import ServiceError
from services.schemas.company import CompanyFilters
from services.schemas.career_profile import CareerProfile

logger = logging.getLogger(__name__)

OPENAI_FILTER_MODEL = os.getenv("OPENAI_FILTER_MODEL", "gpt-5.6-luna")
DEFAULT_JOB_POSTED_WITHIN_DAYS = int(os.getenv("JOB_POSTED_WITHIN_DAYS", "30"))
MAX_OUTPUT_TOKENS = 4000

PROMPT = """\
You are helping a job seeker find companies to apply to. Translate their
free-text description of the companies they want into Apollo.io organization
search filters.

Job seeker's description:
{query}
{background}
Return JSON matching the given schema. Each field maps to a REAL Apollo.io
filter — only use the semantics described:
- hiring_locations: where the job seeker wants to work, i.e. the locations
  of the jobs the COMPANY is hiring for (country or city, Apollo's own
  spelling e.g. "united arab emirates"). A place in the description normally
  goes here: "companies in Dubai", "jobs in India", "Bengaluru startups" ->
  hiring_locations. Keep the place as specific as the description: a city
  stays a city. Apollo can't search remote jobs, so never put "remote"
  here; for "remote" alone leave it empty.
- company_locations: where the COMPANY is headquartered. ONLY when the
  description is explicitly about the company's base or nationality —
  "headquartered in India", "HQ in the US", "an Indian company", "US-based
  companies hiring in Dubai" -> company_locations ["india"] / ["united
  states"]. Otherwise leave it empty; most people will happily work for a
  company headquartered elsewhere.
- employee_ranges: company headcount as "min,max" strings (e.g. "1,200").
  This is a free numeric range, not a fixed catalog of buckets — pick min/max
  values that match the description directly rather than snapping to a
  preset size.
- job_title_signals: the roles the job seeker wants, i.e. job titles the
  COMPANY is HIRING for right now. Write them as concrete job titles; expand a
  role family into the 2-4 most common titles (e.g. "sales roles" -> "sales
  manager", "account executive", "business development manager"; "backend
  engineer" -> "backend engineer", "software engineer"). Leave empty if no
  role is mentioned.
- keyword_tags: short company industry/category keywords (e.g. "logistics",
  "insurance", "real estate") — free-text, not the business-model
  classification below. If a term matches one of the market_segments values
  below, put it ONLY in market_segments, never in both.
- market_segments: business-model classification — ONLY from this exact
  list: b2b, b2c, b2b2c, e-commerce, fintech, d2c, non-profit, saas,
  consulting, services, retail. Leave empty if the description doesn't imply
  one of these. A plain industry like "logistics" or "insurance" is a
  keyword_tag, not a market segment — but a term that IS one of these 11
  values goes here only, not in keyword_tags too.
- min_active_job_postings: minimum number of currently active job postings
  the company should have, only if the description implies a growth/
  hiring-volume signal (e.g. "hiring aggressively", "lots of open roles") —
  otherwise null.
- job_posted_within_days: only if the description says the jobs were posted
  recently — "posted this week" -> 7, "posted this month" -> 30, "recently
  posted" -> 30 — otherwise null.
- founded_year_min / founded_year_max: inclusive bounds on the year the
  company was founded (the current year is {current_year}).
  "founded from/since 2020" or "2020 onwards" -> min 2020;
  "founded before 2015" -> max 2014; "founded in 2018" -> min and max 2018;
  "founded in the last 5 years" -> min {five_years_ago}.
  Leave both null unless the description explicitly mentions when the
  company was founded/established.
"""

BACKGROUND = """
Job seeker's background, extracted from their résumé:
{profile}

Use the background ONLY for filters the description leaves open. Whatever the
description says always wins: if it names a role, location, size or industry,
use that and ignore the background for that filter. If the description is
empty, build every filter you can from the background:
- job_title_signals: 2-4 titles for their function and current title at their
  seniority (e.g. senior + engineering + "Backend Engineer" -> "senior
  software engineer", "senior backend engineer"). Skills only help choose the
  titles; never put skills in keyword_tags.
- hiring_locations: open_to_locations, else the country from location.
  Never fill company_locations from the background.
- employee_ranges: the company_size_history buckets as given.
- keyword_tags: industries.
Never derive market_segments, job posting counts, posting recency or
founding years from the background.
"""

NO_DESCRIPTION = "(none — search from the background below)"


class FilterGenerationError(ServiceError):
    status_code = 400


def _background(profile: Optional[CareerProfile]) -> str:
    if profile is None or profile.is_empty():
        return ""
    return BACKGROUND.format(profile=profile.model_dump_json(indent=2))


async def generate_filters(
    query: str, user_id: int, profile: Optional[CareerProfile] = None
) -> CompanyFilters:
    current_year = date.today().year
    prompt = PROMPT.format(
        query=query or NO_DESCRIPTION,
        background=_background(profile),
        current_year=current_year,
        five_years_ago=current_year - 5,
    )

    try:
        response = await openai_client.client().responses.parse(
            model=OPENAI_FILTER_MODEL,
            reasoning={"effort": "low"},
            input=prompt,
            text_format=CompanyFilters,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            store=False,
            safety_identifier=openai_client.safety_identifier(user_id),
        )
    except ServiceError:
        raise
    except Exception as exc:
        logger.exception("Filter LLM call failed")
        raise FilterGenerationError("Couldn't turn that description into filters, try again") from exc

    openai_client.log_usage("Filter", OPENAI_FILTER_MODEL, response.usage, user_id)
    if response.output_parsed is None:
        raise FilterGenerationError("Couldn't turn that description into filters, try rephrasing it")
    return response.output_parsed
