import pytest
from openai.lib._pydantic import to_strict_json_schema
from pydantic import ValidationError

from services.schemas.common import MAX_ITEMS
from services.schemas.company import CompanyFilters
from tests.conftest import make_filters


def test_strict_schema_requires_every_field_and_enumerates_segments():
    schema = to_strict_json_schema(CompanyFilters)

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert "description" not in schema
    assert len(schema["properties"]["market_segments"]["items"]["enum"]) == 11


def test_text_lists_are_trimmed_deduplicated_and_capped():
    filters = make_filters(
        job_title_signals=["  Sales   Manager ", "sales manager", "", "x" * 101]
        + [f"role {i}" for i in range(20)]
    )

    assert filters.job_title_signals[0] == "Sales Manager"
    assert "sales manager" not in filters.job_title_signals
    assert "x" * 101 not in filters.job_title_signals
    assert len(filters.job_title_signals) == MAX_ITEMS


def test_employee_ranges_are_normalized():
    filters = make_filters(
        employee_ranges=["10-200", "500+", "200,10", "abc", "0,10", "10 – 200"]
    )

    assert filters.employee_ranges == ["10,200", "500,1000000", "1,10"]


def test_out_of_range_numbers_are_dropped_or_clamped():
    filters = make_filters(
        min_active_job_postings=0,
        job_posted_within_days=5000,
        founded_year_min=2022,
        founded_year_max=2015,
    )

    assert filters.min_active_job_postings is None
    assert filters.job_posted_within_days == 365
    assert (filters.founded_year_min, filters.founded_year_max) == (2015, 2022)
    assert make_filters(founded_year_min=1200).founded_year_min is None
    assert make_filters(job_posted_within_days=0).job_posted_within_days is None


def test_blank_only_filters_count_as_empty():
    assert make_filters(company_locations=["  "], job_title_signals=[""]).is_empty()
    assert not make_filters(company_locations=["dubai"]).is_empty()


def test_unknown_market_segment_is_rejected():
    with pytest.raises(ValidationError):
        make_filters(market_segments=["ecommerce"])
