"""Community Crawler Adapter 오케스트레이터.

파이프라인: 발견(Naver 웹검색) → fetch(robots/rate-limit 게이트) → 파싱(공개 HTML
본문만) → 정규화 → SQLite 저장. 각 사이트는 정책(enabled/robots/제외규칙)을
따르며, 비활성 사이트는 건너뛴다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from .discovery import NaverWebDiscovery
from .fetch import PoliteFetcher
from .policy import SitePolicy, load_policies
from .sites import get_parser
from .store import CommunityPost, CommunityStore

log = logging.getLogger(__name__)


@dataclass
class AdapterStats:
    discovered: int = 0
    fetched: int = 0
    parsed: int = 0
    stored: int = 0
    skipped: dict = field(default_factory=dict)

    def skip(self, reason: str):
        self.skipped[reason] = self.skipped.get(reason, 0) + 1


class CommunityAdapter:
    def __init__(self, db_path: str, policies: dict[str, SitePolicy] | None = None,
                 config_path: str | None = None):
        self.policies = policies or load_policies(config_path)
        self.store = CommunityStore(db_path)
        self.discovery = NaverWebDiscovery()

    def run(self, keywords: list[str], start: date | None = None,
            end: date | None = None) -> AdapterStats:
        stats = AdapterStats()
        enabled = [n for n, p in self.policies.items() if p.enabled]
        if not enabled:
            log.info("커뮤니티 수집: 활성 사이트 없음(모든 사이트 enabled=false). "
                     "운영자가 robots/이용약관 검토 후 config/community.yaml 에서 활성화 필요.")
            return stats

        candidates = self.discovery.discover(keywords, self.policies)
        stats.discovered = len(candidates)

        fetchers = {n: PoliteFetcher(self.policies[n]) for n in enabled}
        for cand in candidates:
            fetcher = fetchers.get(cand.site)
            if fetcher is None:
                continue
            res = fetcher.fetch(cand.url)
            if not res.ok:
                stats.skip(res.skipped_reason or f"status {res.status}")
                continue
            stats.fetched += 1
            content = get_parser(cand.site).parse(res.html)
            if not content.ok:
                stats.skip("본문 파싱 실패")
                continue
            stats.parsed += 1
            pol = self.policies[cand.site]
            post = CommunityPost(
                site=cand.site, url=cand.url,
                title=content.title or cand.title,
                body=content.body,
                posted_at=content.posted_at,
                views=content.views, likes=content.likes,
                comment_count=content.comment_count,
                keyword=keywords[0] if keywords else "",
            )
            # 개인정보 미수집: author/댓글 텍스트는 애초에 파서가 추출하지 않음
            self.store.upsert(post)
            stats.stored += 1
        log.info("커뮤니티 수집 완료: 발견 %d / fetch %d / 파싱 %d / 저장 %d / 스킵 %s",
                 stats.discovered, stats.fetched, stats.parsed, stats.stored, stats.skipped)
        return stats
