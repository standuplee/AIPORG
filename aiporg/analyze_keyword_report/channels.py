from __future__ import annotations

from collections import defaultdict

from ..models import Document
from ..models_keyword_report import ChannelTrendItem
from .keywords import top_ranked_keywords


def build_channel_trends(
    current_docs: list[Document],
    previous_docs: list[Document],
) -> list[ChannelTrendItem]:
    current_by_channel: dict[str, list[Document]] = defaultdict(list)
    previous_counts: dict[str, int] = defaultdict(int)

    for doc in current_docs:
        current_by_channel[doc.channel.value].append(doc)
    for doc in previous_docs:
        previous_counts[doc.channel.value] += 1

    items: list[ChannelTrendItem] = []
    for channel, docs in sorted(current_by_channel.items(), key=lambda item: (-len(item[1]), item[0])):
        prev_count = previous_counts.get(channel, 0)
        current_count = len(docs)
        items.append(
            ChannelTrendItem(
                channel=channel,
                share_or_volume=current_count,
                change_direction=_change_direction(current_count, prev_count),
                change_pct=_change_pct(current_count, prev_count),
                keywords=[item.keyword for item in top_ranked_keywords(docs, top_n=3)],
            )
        )
    return items


def _change_direction(current_count: int, previous_count: int) -> str:
    if previous_count == 0:
        return "비교 불가"
    if current_count > previous_count:
        return "▲ 증가"
    if current_count < previous_count:
        return "▼ 감소"
    return "— 유지"


def _change_pct(current_count: int, previous_count: int) -> float | None:
    if previous_count == 0:
        return None
    return round(((current_count - previous_count) / previous_count) * 100, 2)
