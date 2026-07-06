"""공공 RSS / 정부 보도자료 수집기 (인증 불필요, 실수집)."""
from __future__ import annotations

import hashlib
from datetime import date, datetime

from ..models import Channel, Document
from .base import BaseCollector

# 지자체/정부 보도자료 RSS 예시. 운영 시 대상 기관에 맞게 config 로 주입.
DEFAULT_FEEDS = [
    "https://www.korea.kr/rss/dept_chungnam.xml",
]


class PublicRssCollector(BaseCollector):
    name = "public_rss"
    channel = Channel.RSS

    def __init__(self, max_docs: int = 200, timeout: int = 10, feeds: list[str] | None = None):
        super().__init__(max_docs, timeout)
        self.feeds = feeds or DEFAULT_FEEDS

    def collect(self, keywords: list[str], start: date, end: date) -> list[Document]:
        import feedparser

        docs: list[Document] = []
        for feed_url in self.feeds:
            feed = feedparser.parse(feed_url)
            for e in feed.entries:
                text = getattr(e, "title", "") + getattr(e, "summary", "")
                if keywords and not any(k in text for k in keywords):
                    continue
                published = None
                if getattr(e, "published_parsed", None):
                    published = datetime(*e.published_parsed[:6])
                    if published.date() < start or published.date() > end:
                        continue
                link = getattr(e, "link", "")
                docs.append(Document(
                    doc_id=hashlib.sha1(link.encode()).hexdigest()[:16],
                    channel=self.channel, title=getattr(e, "title", ""),
                    body=getattr(e, "summary", ""), url=link, published_at=published,
                    matched_keywords=[k for k in keywords if k in text],
                ))
        return docs
