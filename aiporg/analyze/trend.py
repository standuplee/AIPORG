"""트렌드 분석 (PRD 7-⑧): 급상승/급감/신규 키워드."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrendItem:
    keyword: str
    current: int
    previous: int

    @property
    def change_pct(self) -> float:
        if self.previous == 0:
            return 100.0
        return round((self.current - self.previous) / self.previous * 100, 1)


def compute_trends(current: dict[str, int], previous: dict[str, int]):
    """현재/전월 키워드 빈도 비교로 급상승·급감·신규 분류."""
    rising, falling, new = [], [], []
    for kw, cur in current.items():
        prev = previous.get(kw, 0)
        item = TrendItem(kw, cur, prev)
        if prev == 0 and cur > 0:
            new.append(item)
        elif item.change_pct >= 30:
            rising.append(item)
        elif item.change_pct <= -30:
            falling.append(item)
    rising.sort(key=lambda x: x.change_pct, reverse=True)
    falling.sort(key=lambda x: x.change_pct)
    return {"rising": rising, "falling": falling, "new": new}
