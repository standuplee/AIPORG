"""1차 MVP: Naver 웹 검색 API 로 커뮤니티 글 URL 발견.

공식 커뮤니티 API 를 쓰지 않고, Naver 웹문서 검색 결과에서 대상 커뮤니티
도메인에 해당하는 URL 만 필터링한다. (URL 발견까지만; 본문은 fetch/parse 단계)
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from .policy import SitePolicy

log = logging.getLogger(__name__)


@dataclass
class Candidate:
    site: str
    url: str
    title: str
    snippet: str


def _strip(s: str) -> str:
    import html
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


class NaverWebDiscovery:
    """Naver webkr 검색으로 사이트별 후보 URL 수집."""

    ENDPOINT = "https://openapi.naver.com/v1/search/webkr.json"

    def __init__(self, display: int = 50):
        self.display = display
        self.cid = os.environ.get("NAVER_CLIENT_ID")
        self.secret = os.environ.get("NAVER_CLIENT_SECRET")

    @property
    def available(self) -> bool:
        return bool(self.cid and self.secret)

    def discover(self, keywords: list[str], policies: dict[str, SitePolicy]) -> list[Candidate]:
        if not self.available:
            log.warning("NAVER 키 없음 → 커뮤니티 URL 발견 불가")
            return []
        import requests

        headers = {"X-Naver-Client-Id": self.cid, "X-Naver-Client-Secret": self.secret}
        seen: set[str] = set()
        out: list[Candidate] = []
        enabled = {n: p for n, p in policies.items() if p.enabled}
        if not enabled:
            log.info("활성화된 커뮤니티 사이트 없음(enabled=true 필요) → 발견 0")
            return []

        for name, pol in enabled.items():
            for kw in keywords[:3]:
                for hint in pol.search_hints[:2]:
                    query = f"{kw} {hint}"
                    try:
                        r = requests.get(self.ENDPOINT, headers=headers,
                                         params={"query": query, "display": self.display},
                                         timeout=pol.request_timeout_sec)
                        r.raise_for_status()
                    except Exception as e:  # noqa: BLE001
                        log.warning("[discover:%s] 검색 실패: %s", name, e)
                        continue
                    for it in r.json().get("items", []):
                        link = it.get("link", "")
                        host = urlparse(link).netloc.lower()
                        if not pol.matches_domain(host):
                            continue
                        if pol.is_excluded(link) or link in seen:
                            continue
                        seen.add(link)
                        out.append(Candidate(
                            site=name, url=link,
                            title=_strip(it.get("title", "")),
                            snippet=_strip(it.get("description", "")),
                        ))
        log.info("커뮤니티 URL 발견: %d건 (사이트 %s)", len(out), ", ".join(enabled))
        return out
