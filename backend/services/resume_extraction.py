import base64
import logging
import os
from datetime import date
from typing import Optional

from pydantic import BaseModel

from services import openai_client
from services.errors import ServiceError
from services.schemas.career_profile import CareerProfile, CompanySize, JobFunction, Seniority
from services.schemas.user_profile import ResumeDetails

logger = logging.getLogger(__name__)

OPENAI_RESUME_MODEL = os.getenv(
    "OPENAI_RESUME_MODEL", os.getenv("OPENAI_FILTER_MODEL", "gpt-5.6-luna")
)
MAX_OUTPUT_TOKENS = 4000
DETAILS_MAX_OUTPUT_TOKENS = 8000

# Upper headcount bound of each bucket; anything bigger lands in the largest one
SIZE_BUCKETS: list[tuple[int, CompanySize]] = [
    (10, "1,10"),
    (50, "11,50"),
    (200, "51,200"),
    (500, "201,500"),
    (1000, "501,1000"),
    (5000, "1001,5000"),
    (10000, "5001,10000"),
]

PROMPT = """\
The attached PDF is a job seeker's résumé. Extract their career profile; it
will be used to find companies that are hiring people like them. Today is
{today}.

Return JSON matching the given schema, filling the fields in order. Use only
what the résumé says or clearly implies; use null or an empty list rather
than guessing, except where a field below asks for a best estimate.
- years_of_experience: total years of professional work, from the start of
  their first job to today (or the end of their last job). Count overlapping
  roles once; leave out education, internships and side projects.
- employers: every company they have worked at, most recent first, one entry
  per company (internships and freelance work excluded). employees is your
  best estimate of the company's headcount while they worked there; always
  give one. Use what you know about the company first, then résumé cues:
  "founding"/"first engineer", "seed-stage", "team of 12", "Fortune 500",
  "unicorn", the scale of what they built. A company you don't recognise is
  usually small — a startup, agency or non-profit — so estimate low (10-50)
  unless the cues say otherwise. The user reviews these, so a rough number
  beats none; null only if the company name itself is unreadable.
- current_title: their current (or most recent) job title, as written.
- seniority: decide from years_of_experience first, then from their roles.
  Years set the ceiling:
    under 4 years  -> entry, whatever the title says
    4+ years       -> senior
    6+ years       -> manager, if they manage people
    8+ years       -> head or director, if their roles are at that level
    12+ years      -> vp or c_suite, if their roles are at that level
  Within that ceiling, use their current role, then past roles: a title
  above what their years support (e.g. "CTO" or "Lead" with 2 years) does
  not raise the level, and an individual contributor with 10 years is senior
  (entry covers individual contributors up to mid-level; senior covers
  senior/staff/principal/lead individual contributors).
- function: the department their current role belongs to.
- top_skills: up to 10 skills most central to their work, most important
  first (tools, languages, domains — not soft skills).
- industries: up to 5 industries they have worked in, short lowercase
  keywords (e.g. "fintech", "logistics", "healthcare").
- location: where they live now, "city, country" when given.
- open_to_locations: where they could work, used to search for companies
  hiring there. The places they explicitly say they would work or relocate
  to, plus the country they live in; if they name none, just that country.
  Prefer countries over cities unless they single out a city. Never
  "remote": remote jobs can't be searched, so "open to remote" means their
  own country.
"""

DETAILS_PROMPT = """\
The attached PDF is a job seeker's résumé. Fill in their profile from it; they
will review and edit it. Today is {today}.

Use only what the résumé says. Use an empty string, 0, an empty list or null
for anything it doesn't give, except where a field below asks you to write
something.
- name, email, phone: as written.
- headline: their current title and specialty in under 10 words, e.g.
  "Senior Backend Engineer · payments and APIs".
- location: where they live now, "city, country".
- timezone: whichever of these matches where they live, or "" if none does.
- linkedin, portfolio: full URLs as written. portfolio is a personal site,
  GitHub or similar.
- bio: two short first-person sentences on who they are and what they do,
  under 280 characters.
- pitch: one first-person sentence they could open an email to a hiring
  manager with, built on their strongest concrete result in the résumé (with
  its number if it has one). Never invent a result; without one, say plainly
  what they do and for whom.
- years_experience: whole years of professional work, overlapping roles
  counted once, education and internships left out.
- current_company: where they work now, or "" if they aren't working.
- roles: every job, most recent first. start and end as "Mon YYYY", or just
  "YYYY" if that's all it gives; end is "Present" for a current job.
  highlights: up to 4 short achievements, tightened but keeping any numbers.
  skills: up to 6 tools or skills used in that job.
- education: their highest qualification; years as "YYYY – YYYY" or the end
  year alone.
- target_roles: up to 3 job titles they'd most likely apply for next: their
  current title, and one level up if their experience supports it.
- target_seniority: the levels they'd apply at, from Mid, Senior, Staff and
  Principal. Empty if none fit (for example a people manager or a graduate).
- target_locations: where they want to work: the places they say they'd work
  or move to, plus the country they live in. country is the full English
  name; city only if they single one out, otherwise null.
- open_to_remote: true only if the résumé says they're open to remote work.
"""


class Employer(BaseModel):
    name: str
    employees: Optional[int]


class ResumeExtraction(BaseModel):
    """What the LLM fills in. Years and employers come first so the model
    works them out before choosing seniority; they're turned into the
    profile's company_size_history and otherwise dropped."""

    years_of_experience: Optional[float]
    employers: list[Employer]
    current_title: Optional[str]
    seniority: Optional[Seniority]
    function: Optional[JobFunction]
    top_skills: list[str]
    industries: list[str]
    location: Optional[str]
    open_to_locations: list[str]

    def to_profile(self) -> CareerProfile:
        return CareerProfile(
            **self.model_dump(exclude={"years_of_experience", "employers"}),
            company_size_history=size_buckets(self.employers),
        )


class ResumeExtractionError(ServiceError):
    status_code = 422


def size_bucket(employees: Optional[int]) -> Optional[CompanySize]:
    if employees is None or employees < 1:
        return None
    for upper, bucket in SIZE_BUCKETS:
        if employees <= upper:
            return bucket
    return SIZE_BUCKETS[-1][1]


def size_buckets(employers: list[Employer]) -> list[CompanySize]:
    buckets: list[CompanySize] = []
    for employer in employers:
        bucket = size_bucket(employer.employees)
        if bucket is not None:
            buckets.append(bucket)
    return buckets


async def extract_profile(pdf: bytes, file_name: str, user_id: int) -> CareerProfile:
    file_data = "data:application/pdf;base64," + base64.b64encode(pdf).decode()
    try:
        response = await openai_client.client().responses.parse(
            model=OPENAI_RESUME_MODEL,
            reasoning={"effort": "low"},
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "filename": file_name, "file_data": file_data},
                        {"type": "input_text", "text": PROMPT.format(today=date.today().isoformat())},
                    ],
                }
            ],
            text_format=ResumeExtraction,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            store=False,
            safety_identifier=openai_client.safety_identifier(user_id),
        )
    except ServiceError:
        raise
    except Exception as exc:
        logger.exception("Résumé LLM call failed")
        raise ResumeExtractionError("Couldn't read that résumé, try again") from exc

    openai_client.log_usage("Résumé", OPENAI_RESUME_MODEL, response.usage, user_id)
    extraction = response.output_parsed
    if extraction is None:
        raise ResumeExtractionError("Couldn't find any career details in that résumé")
    logger.info(
        "Résumé for user %s: %s years, %d employers (%d sized)",
        user_id,
        extraction.years_of_experience,
        len(extraction.employers),
        sum(employer.employees is not None for employer in extraction.employers),
    )
    profile = extraction.to_profile()
    if profile.is_empty():
        raise ResumeExtractionError("Couldn't find any career details in that résumé")
    return profile


async def extract_details(pdf: bytes, file_name: str, user_id: int) -> ResumeDetails:
    file_data = "data:application/pdf;base64," + base64.b64encode(pdf).decode()
    try:
        response = await openai_client.client().responses.parse(
            model=OPENAI_RESUME_MODEL,
            reasoning={"effort": "low"},
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "filename": file_name, "file_data": file_data},
                        {
                            "type": "input_text",
                            "text": DETAILS_PROMPT.format(today=date.today().isoformat()),
                        },
                    ],
                }
            ],
            text_format=ResumeDetails,
            max_output_tokens=DETAILS_MAX_OUTPUT_TOKENS,
            store=False,
            safety_identifier=openai_client.safety_identifier(user_id),
        )
    except ServiceError:
        raise
    except Exception as exc:
        logger.exception("Résumé details LLM call failed")
        raise ResumeExtractionError("Couldn't read that résumé's details") from exc

    openai_client.log_usage("Résumé details", OPENAI_RESUME_MODEL, response.usage, user_id)
    if response.status == "incomplete" or response.output_parsed is None:
        raise ResumeExtractionError("Couldn't read that résumé's details")
    return response.output_parsed
