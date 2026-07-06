"""토픽 분류 (12개 카테고리, 사전 기반)."""
from __future__ import annotations

from collections import Counter

from ..config import TOPIC_CATEGORIES
from ..schema import TopicStat, Video

LEXICON: dict[str, list[str]] = {
    "행정": ["행정", "조직", "청사", "도청", "통합", "공무원", "민원", "정책"],
    "경제": ["경제", "투자", "예산", "일자리", "물가", "국비", "재정", "소상공인"],
    "산업": ["산업", "반도체", "기업", "공장", "제조", "데이터센터", "특화", "ai"],
    "복지": ["복지", "돌봄", "노인", "보육", "장애", "취약", "지원금", "요양"],
    "환경": ["환경", "탄소", "발전", "석탄", "에너지", "기후", "미세먼지", "재생"],
    "선거": ["선거", "공천", "후보", "출마", "당선", "민선", "지방선거", "표"],
    "교육": ["교육", "학교", "대학", "학생", "교사", "돌봄교실", "입시"],
    "문화": ["문화", "축제", "예술", "공연", "체육", "전시", "행사"],
    "교통": ["교통", "도로", "철도", "버스", "지하철", "국도", "고속도로", "교량"],
    "관광": ["관광", "여행", "축제", "명소", "숙박", "야간경제", "관광객"],
    "재난": ["재난", "화재", "사고", "폭우", "지진", "안전", "소방", "구조"],
}


def classify_video(video: Video) -> str:
    text = f"{video.title} {video.description}".lower()
    scores = {cat: sum(text.count(w) for w in words) for cat, words in LEXICON.items()}
    best = max(scores, key=scores.get) if scores else "기타"
    return best if scores.get(best, 0) > 0 else "기타"


def distribution(videos: list[Video], top_n: int = 6) -> list[TopicStat]:
    counter: Counter = Counter()
    views: Counter = Counter()
    for v in videos:
        topic = v.topic or classify_video(v)
        counter[topic] += 1
        views[topic] += v.view_count
    total = sum(counter.values()) or 1
    stats = [TopicStat(topic=t, video_count=c, view_sum=views[t],
                       ratio=round(c / total * 100, 1))
             for t, c in counter.most_common(top_n)]
    return stats


def valid_categories() -> list[str]:
    return list(TOPIC_CATEGORIES)
