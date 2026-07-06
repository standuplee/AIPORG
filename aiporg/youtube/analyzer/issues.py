"""핵심 이슈 점수 계산 및 TOP10.

Issue Score = 조회수 30% + 댓글수 25% + 영상수 20% + 키워드빈도 15% + 감성강도 10%
각 지표는 후보 키워드 간 0~1 정규화 후 가중합한다.
"""
from __future__ import annotations

from . import sentiment as S
from . import topics as T
from ..schema import Comment, IssueStat, KeywordStat, Video

W_VIEWS, W_COMMENTS, W_VIDEOS, W_FREQ, W_SENT = 0.30, 0.25, 0.20, 0.15, 0.10


def _norm(values: dict[str, float]) -> dict[str, float]:
    mx = max(values.values(), default=0.0)
    if mx <= 0:
        return {k: 0.0 for k in values}
    return {k: v / mx for k, v in values.items()}


def compute(videos: list[Video], comments: list[Comment],
            keyword_stats: list[KeywordStat], top_n: int = 10) -> list[IssueStat]:
    candidates = keyword_stats[: max(top_n * 2, 20)]
    if not candidates:
        return []

    comments_by_video: dict[str, list[Comment]] = {}
    for c in comments:
        comments_by_video.setdefault(c.video_id, []).append(c)

    views, comm, vids, freq, sent = {}, {}, {}, {}, {}
    meta: dict[str, dict] = {}
    for ks in candidates:
        kw = ks.keyword
        matched = [v for v in videos if kw in f"{v.title} {v.description}"]
        if not matched:
            continue
        labels = [v.sentiment or S.classify(v.title) for v in matched]
        for v in matched:
            labels += [c.sentiment or "중립" for c in comments_by_video.get(v.video_id, [])]
        views[kw] = float(sum(v.view_count for v in matched))
        comm[kw] = float(sum(v.comment_count for v in matched))
        vids[kw] = float(len(matched))
        freq[kw] = float(ks.frequency)
        sent[kw] = S.intensity(labels)
        topic = T.distribution(matched, top_n=1)
        meta[kw] = {
            "topic": topic[0].topic if topic else "기타",
            "view_sum": int(views[kw]), "comment_sum": int(comm[kw]),
            "video_count": len(matched),
            "sentiment": _dominant(labels),
        }

    nv, nc, nvi, nf, ns = _norm(views), _norm(comm), _norm(vids), _norm(freq), _norm(sent)
    scored = []
    for kw in meta:
        score = (W_VIEWS * nv.get(kw, 0) + W_COMMENTS * nc.get(kw, 0)
                 + W_VIDEOS * nvi.get(kw, 0) + W_FREQ * nf.get(kw, 0)
                 + W_SENT * ns.get(kw, 0))
        scored.append((score, kw))
    scored.sort(reverse=True)

    issues = []
    for rank, (score, kw) in enumerate(scored[:top_n], 1):
        m = meta[kw]
        issues.append(IssueStat(
            rank=rank, keyword=kw, topic=m["topic"], score=round(score, 4),
            view_sum=m["view_sum"], comment_sum=m["comment_sum"],
            video_count=m["video_count"], sentiment=m["sentiment"]))
    return issues


def _dominant(labels: list[str]) -> str:
    if not labels:
        return "중립"
    pos, neg = labels.count("긍정"), labels.count("부정")
    if pos == 0 and neg == 0:
        return "중립"
    if pos and neg and abs(pos - neg) <= max(1, int(0.1 * len(labels))):
        return "혼재"
    return "긍정" if pos > neg else "부정"
