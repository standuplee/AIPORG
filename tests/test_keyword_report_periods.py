from datetime import date

from aiporg.analyze_keyword_report.periods import previous_month_range


def test_previous_month_range_for_july():
    start, end = previous_month_range(date(2026, 7, 1), date(2026, 7, 31))
    assert start.isoformat() == "2026-06-01"
    assert end.isoformat() == "2026-06-30"
