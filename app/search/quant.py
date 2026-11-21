"""Volume and trend figures computed only from the collected relevant posts; no LLM, no web."""

from collections import Counter
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import Field

from app.schemas.common import SchemaBase

KST = ZoneInfo("Asia/Seoul")
MIN_TREND_POSTS = 5  # fewer dated posts than this say nothing about a trend
BASIS = ("수집된 관련 글(블로그·카페 검색 결과) 기준이며 온라인 전체 언급량이 아니다. "
         "추이는 게시일이 확인된 글만 집계했고, 비교 기간 자료가 없어 증감률은 산출하지 않았다.")


class QuantitativeResult(SchemaBase):
    basis: str = BASIS
    start_date: date
    end_date: date
    total_posts: int
    by_channel: dict[str, int]
    dated_posts: int  # posts with a publish date inside the period
    undated_posts: int
    out_of_period_posts: int
    daily: dict[str, int]  # ISO date -> posts, zeros included across the period
    weekly: dict[str, int]  # Monday's ISO date -> posts
    weekly_by_channel: dict[str, dict[str, int]] = Field(default_factory=dict)


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def build_quantitative(posts: list, start: date, end: date) -> QuantitativeResult:
    """`posts` need `channel` and `published_at` (aware datetime or None); dates are read in KST."""
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    weeks = list(dict.fromkeys(_monday(d) for d in days))
    daily, weekly = Counter(), Counter()
    by_week_channel: dict[str, Counter] = {}
    undated = outside = 0
    for p in posts:
        at: datetime | None = p.published_at
        if at is None:
            undated += 1
            continue
        d = at.astimezone(KST).date()
        if not start <= d <= end:
            outside += 1
            continue
        daily[d] += 1
        weekly[_monday(d)] += 1
        by_week_channel.setdefault(p.channel, Counter())[_monday(d)] += 1
    return QuantitativeResult(
        start_date=start, end_date=end, total_posts=len(posts), by_channel=dict(Counter(p.channel for p in posts)),
        dated_posts=sum(daily.values()), undated_posts=undated, out_of_period_posts=outside,
        daily={d.isoformat(): daily[d] for d in days}, weekly={w.isoformat(): weekly[w] for w in weeks},
        weekly_by_channel={c: {w.isoformat(): n[w] for w in weeks} for c, n in by_week_channel.items()},
    )


def volume_lines(q: QuantitativeResult) -> list[str]:
    """Report sentences made only of the counts above."""
    channels = ", ".join(f"{c} {n}건" for c, n in sorted(q.by_channel.items(), key=lambda kv: (-kv[1], kv[0])))
    lines = [f"수집된 관련 글 {q.total_posts}건 ({channels or '해당 없음'})", f"게시일 확인 {q.dated_posts}건 / 게시일 미확인 {q.undated_posts}건"
             + (f" / 분석 기간 밖 {q.out_of_period_posts}건 제외" if q.out_of_period_posts else "")]
    if q.dated_posts < MIN_TREND_POSTS:
        return lines + [f"게시일이 확인된 글이 {q.dated_posts}건뿐이라 시간별 추이는 산출하지 않았다."]
    peak = max(q.weekly.values())
    lines.append("주별 게시 건수(월요일 시작): " + ", ".join(f"{w[5:]} {n}건" for w, n in q.weekly.items()))
    lines.append("가장 많은 주: " + ", ".join(f"{w[5:]}주 {n}건" for w, n in q.weekly.items() if n == peak))
    return lines
