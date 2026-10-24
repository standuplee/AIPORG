from datetime import date, timedelta, timezone

from app.search.schemas import PeriodStatus, SearchResult

_KST = timezone(timedelta(hours=9))


def classify_period(
    result: SearchResult, start: date, end: date, *, allow_historical: bool = False
) -> PeriodStatus:
    if result.published_at is None:
        return PeriodStatus.UNKNOWN
    published = result.published_at.astimezone(_KST).date()
    if start <= published <= end:
        return PeriodStatus.IN_PERIOD
    if published < start and allow_historical:
        return PeriodStatus.HISTORICAL_ALLOWED
    return PeriodStatus.OUT_OF_PERIOD
