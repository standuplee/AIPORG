"""YouTube 수집·분석 설정 및 Quota 제한 상수."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


# --- Quota 절약 하드 제한 (스펙 준수) --------------------------------------- #
MAX_KEYWORDS: int = 9
VIDEOS_PER_KEYWORD: int = 10
MAX_TOTAL_VIDEOS: int = 60
VIDEOS_BATCH_SIZE: int = 50
COMMENT_TARGET_VIDEOS: int = 15          # 조회수 상위 N개만 댓글 수집
MIN_COMMENTS_FOR_COLLECT: int = 5        # 댓글 5개 이상 영상만
MAX_COMMENTS_PER_VIDEO: int = 20
CACHE_TTL_DAYS: int = 30

DEFAULT_KEYWORDS: list[str] = [
    "충남", "충청남도", "충남도청", "충남도지사", "박수현",
    "박수현 충남도지사", "민선9기", "충남도정", "통하는 충남",
]

TOPIC_CATEGORIES: list[str] = [
    "행정", "경제", "산업", "복지", "환경", "선거",
    "교육", "문화", "교통", "관광", "재난", "기타",
]


@dataclass
class YouTubeConfig:
    """단일 수집·분석 실행 설정."""

    keywords: list[str] = field(default_factory=lambda: list(DEFAULT_KEYWORDS))
    period_start: date = date(2026, 6, 1)
    period_end: date = date(2026, 6, 30)
    region_code: str = "KR"
    relevance_language: str = "ko"
    subject_name: str = "충청남도"
    leader_title: str = "도지사"
    leader_name: str = "박수현"
    force: bool = False                  # True 면 캐시 무시 재수집
    db_path: str = "data/youtube.db"
    gemini_model: str = "gemini-2.5-flash"

    def limited_keywords(self) -> list[str]:
        return self.keywords[:MAX_KEYWORDS]

    @property
    def published_after(self) -> str:
        return f"{self.period_start.isoformat()}T00:00:00Z"

    @property
    def published_before(self) -> str:
        return f"{self.period_end.isoformat()}T23:59:59Z"

    def cache_key(self, keyword: str) -> str:
        return f"{keyword}|{self.period_start.isoformat()}|{self.period_end.isoformat()}"
