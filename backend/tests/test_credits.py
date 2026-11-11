from datetime import datetime, timezone

from services.hunt import credits


def test_a_monthly_grant_key_is_one_per_calendar_month():
    first = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
    last = datetime(2026, 11, 30, 23, 59, tzinfo=timezone.utc)
    next_month = datetime(2026, 12, 1, 0, 0, tzinfo=timezone.utc)

    assert credits.monthly_grant(first) == credits.monthly_grant(last) == "monthly:2026-11"
    assert credits.monthly_grant(next_month) == "monthly:2026-12"
