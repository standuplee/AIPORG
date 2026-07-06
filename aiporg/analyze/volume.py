"""언급량 분석 (PRD 7-⑥) 및 채널 비중 집계."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from ..models import Document


def channel_share(docs: list[Document]) -> dict[str, float]:
    if not docs:
        return {}
    c = Counter(d.channel.value for d in docs)
    n = len(docs)
    return {k: round(v / n * 100, 1) for k, v in c.most_common()}


def daily_volume(docs: list[Document], start: date, end: date) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for d in docs:
        if d.published_at:
            key = d.published_at.date().isoformat()
            counts[key] += 1
    # 전체 기간을 0 으로 채워 연속 시계열 보장
    out: dict[str, int] = {}
    cur = start
    from datetime import timedelta
    while cur <= end:
        k = cur.isoformat()
        out[k] = counts.get(k, 0)
        cur += timedelta(days=1)
    return out


def subject_volumes(docs: list[Document], subjects: dict[str, list[str]]) -> dict[str, int]:
    """이슈 그룹(충남도청/충남지사 등)별 언급량."""
    out: dict[str, int] = {}
    for label, kws in subjects.items():
        out[label] = sum(1 for d in docs if any(k in (d.title + d.body) for k in kws))
    return out
