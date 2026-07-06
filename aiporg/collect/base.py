"""수집기 인터페이스 및 레지스트리."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date

from ..models import Channel, Document

log = logging.getLogger(__name__)


class BaseCollector(ABC):
    """모든 채널 수집기의 공통 계약.

    구현체는 keywords/기간을 받아 Document 리스트를 반환한다.
    네트워크·인증 실패 시 예외를 던지지 말고 빈 리스트를 반환하여
    전체 파이프라인이 중단되지 않도록 한다.
    """

    name: str = "base"
    channel: Channel = Channel.NEWS

    def __init__(self, max_docs: int = 200, timeout: int = 10):
        self.max_docs = max_docs
        self.timeout = timeout

    @abstractmethod
    def collect(self, keywords: list[str], start: date, end: date) -> list[Document]:
        ...

    def safe_collect(self, keywords: list[str], start: date, end: date) -> list[Document]:
        try:
            docs = self.collect(keywords, start, end)
            log.info("[%s] 수집 %d건", self.name, len(docs))
            return docs[: self.max_docs]
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            log.warning("[%s] 수집 실패(무시하고 계속): %s", self.name, exc)
            return []


class CollectorRegistry:
    """활성화된 수집기들을 실행하고 결과를 합친다."""

    def __init__(self, collectors: list[BaseCollector]):
        self.collectors = collectors

    def run(self, keywords: list[str], start: date, end: date) -> list[Document]:
        docs: list[Document] = []
        for c in self.collectors:
            docs.extend(c.safe_collect(keywords, start, end))
        return docs


# 지연 임포트로 순환 참조 방지
def build_registry(names: list[str], max_docs: int = 200) -> CollectorRegistry:
    from . import news, sns, blog, community, rss

    catalog: dict[str, type[BaseCollector]] = {
        "naver_news": news.NaverNewsCollector,
        "daum_news": news.DaumNewsCollector,
        "google_news": news.GoogleNewsCollector,
        "x": sns.XCollector,
        "youtube": sns.YouTubeCollector,
        "instagram": sns.InstagramCollector,
        "naver_blog": blog.NaverBlogCollector,
        "community": community.CommunityCollector,
        "public_rss": rss.PublicRssCollector,
    }
    collectors: list[BaseCollector] = []
    for n in names:
        cls = catalog.get(n)
        if cls is None:
            log.warning("알 수 없는 수집기: %s (건너뜀)", n)
            continue
        collectors.append(cls(max_docs=max_docs))
    return CollectorRegistry(collectors)
