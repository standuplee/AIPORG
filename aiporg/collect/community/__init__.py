"""커뮤니티 수집 어댑터 패키지.

공식 API 를 쓰지 않고 (Naver 웹검색 발견 → 공개 HTML 파싱 → 정규화 저장 →
내부 API) 준법 범위에서 커뮤니티 여론을 수집한다.

CommunityCollector: 기존 수집 파이프라인(BaseCollector)에 연결되는 어댑터.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime

from ...models import Channel, Document
from ..base import BaseCollector
from .adapter import CommunityAdapter
from .store import CommunityStore

log = logging.getLogger(__name__)

COMMUNITY_SITES = ["dcinside", "clien", "fmkorea", "theqoo", "ruliweb"]


def _db_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    return os.path.join(root, "data", "community.db")


class CommunityCollector(BaseCollector):
    """어댑터를 실행해 커뮤니티 글을 수집·저장하고 Document 로 반환.

    활성 사이트가 없으면(기본) 저장된 과거 데이터만 조회해 반환한다.
    """

    name = "community"
    channel = Channel.COMMUNITY

    def __init__(self, max_docs: int = 200, timeout: int = 10, db_path: str | None = None):
        super().__init__(max_docs, timeout)
        self.db_path = db_path or _db_path()

    def collect(self, keywords: list[str], start: date, end: date) -> list[Document]:
        adapter = CommunityAdapter(self.db_path)
        adapter.run(keywords, start, end)   # 활성 사이트 없으면 no-op

        store = CommunityStore(self.db_path)
        posts = store.query(start=start.isoformat(), end=end.isoformat(),
                            limit=self.max_docs)
        docs: list[Document] = []
        for p in posts:
            pub = None
            if p.posted_at:
                try:
                    pub = datetime.fromisoformat(p.posted_at)
                except Exception:
                    pub = None
            docs.append(Document(
                doc_id=p.url_hash, channel=self.channel, title=p.title,
                body=p.body, url=p.url, published_at=pub,
                views=p.views, likes=p.likes, comments=p.comment_count,
                matched_keywords=[k for k in keywords if k in (p.title + p.body)],
            ))
        return docs


__all__ = ["CommunityCollector", "CommunityAdapter", "CommunityStore", "COMMUNITY_SITES"]
