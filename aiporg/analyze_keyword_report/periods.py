from __future__ import annotations

from calendar import monthrange
from datetime import date


def previous_month_range(start: date, end: date) -> tuple[date, date]:
    del end
    year = start.year
    month = start.month - 1
    if month == 0:
        year -= 1
        month = 12
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)
