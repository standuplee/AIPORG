"""뉴스 수집기 (네이버/다음/구글).

구글 뉴스 RSS 는 인증 없이 접근 가능하므로 실제 수집을 구현한다.
네이버/다음은 공식 검색 API 키 또는 사내 Lucy 커넥터를 요구하므로,
키가 설정되면 동작하고 없으면 빈 결과로 degrade 하는 형태로 둔다.
"""
from __future__ import annotations

import hashlib
import os
from datetime import date, datetime
from urllib.parse import urlparse
from urllib.parse import quote

from ..models import Channel, Document
from .base import BaseCollector


def _doc_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


class GoogleNewsCollector(BaseCollector):
    """구글 뉴스 RSS 기반 실수집기 (인증 불필요)."""

    name = "google_news"
    channel = Channel.NEWS

    def collect(self, keywords: list[str], start: date, end: date) -> list[Document]:
        import feedparser

        docs: list[Document] = []
        query = " OR ".join(f'"{k}"' for k in keywords[:5])
        url = (
            "https://news.google.com/rss/search?"
            f"q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
        )
        feed = feedparser.parse(url)
        for e in feed.entries:
            published = None
            if getattr(e, "published_parsed", None):
                published = datetime(*e.published_parsed[:6])
                if published.date() < start or published.date() > end:
                    continue
            link = getattr(e, "link", "")
            summary = _strip(getattr(e, "summary", ""))
            title = _strip(getattr(e, "title", ""))
            matched = [k for k in keywords if k in (title + summary)]
            docs.append(Document(
                doc_id=_doc_id(link),
                channel=self.channel,
                title=title,
                body=summary,
                url=link,
                published_at=published,
                author=getattr(e, "source", {}).get("title") if hasattr(e, "source") else None,
                matched_keywords=matched or keywords[:1],
            ))
        return docs


class NaverNewsCollector(BaseCollector):
    """네이버 뉴스 검색 API 수집기.

    NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 있으면 동작한다.
    """

    name = "naver_news"
    channel = Channel.NEWS

    def collect(self, keywords: list[str], start: date, end: date) -> list[Document]:
        cid = os.environ.get("NAVER_CLIENT_ID")
        secret = os.environ.get("NAVER_CLIENT_SECRET")
        if not (cid and secret):
            return []   # 키 없음 -> degrade
        import requests

        docs: list[Document] = []
        headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}
        for kw in keywords[:3]:
            # 최신순 페이징(start=1,101,...)으로 기간(start~end)까지 거슬러 수집.
            # 항목이 기간 시작보다 오래되면 페이징 중단(quota 절약).
            stop = False
            for page in range(1, 1001, 100):
                r = requests.get(
                    "https://openapi.naver.com/v1/search/news.json",
                    params={"query": kw, "display": 100, "start": page, "sort": "date"},
                    headers=headers, timeout=self.timeout,
                )
                if r.status_code != 200:
                    break
                items = r.json().get("items", [])
                if not items:
                    break
                for item in items:
                    pub = _parse_pubdate(item.get("pubDate"))
                    if pub:
                        if pub.date() > end:
                            continue          # 기간보다 최신 → 건너뜀
                        if pub.date() < start:
                            stop = True        # 기간보다 과거 → 이후 중단
                            continue
                    link = item.get("link", "")
                    docs.append(Document(
                        doc_id=_doc_id(link), channel=self.channel,
                        title=_strip(item.get("title", "")),
                        body=_strip(item.get("description", "")),
                        url=link, published_at=pub, matched_keywords=[kw],
                    ))
                if stop or len(items) < 100:
                    break
        return docs


class DaumNewsCollector(BaseCollector):
    """카카오 웹검색 API 기반 다음 뉴스 수집기.

    KAKAO_REST_API_KEY 환경변수가 있으면 동작한다.
    web 검색 결과 전체를 받되, `news.daum.net` 과 `v.daum.net` 링크만 허용한다.
    """

    name = "daum_news"
    channel = Channel.NEWS

    def collect(self, keywords: list[str], start: date, end: date) -> list[Document]:
        api_key = os.environ.get("KAKAO_REST_API_KEY")
        if not api_key:
            return []
        import requests

        docs: list[Document] = []
        headers = {"Authorization": f"KakaoAK {api_key}"}
        allowed_hosts = {"news.daum.net", "v.daum.net"}
        for kw in keywords[:3]:
            for page in range(1, 4):
                r = requests.get(
                    "https://dapi.kakao.com/v2/search/web",
                    params={"query": kw, "size": 50, "page": page, "sort": "recency"},
                    headers=headers,
                    timeout=self.timeout,
                )
                if r.status_code != 200:
                    break
                payload = r.json()
                items = payload.get("documents", [])
                if not items:
                    break
                stop = False
                for item in items:
                    link = item.get("url", "")
                    if urlparse(link).netloc not in allowed_hosts:
                        continue
                    pub = _parse_kakao_datetime(item.get("datetime"))
                    if pub:
                        if pub.date() > end:
                            continue
                        if pub.date() < start:
                            stop = True
                            continue
                    title = _strip(item.get("title", ""))
                    body = _strip(item.get("contents", ""))
                    docs.append(Document(
                        doc_id=_doc_id(link),
                        channel=self.channel,
                        title=title,
                        body=body,
                        url=link,
                        published_at=pub,
                        matched_keywords=[kw],
                    ))
                if stop or payload.get("meta", {}).get("is_end", False):
                    break
        return docs


def _parse_pubdate(value):
    """네이버 뉴스 pubDate (RFC822) -> datetime. 실패 시 None."""
    if not value:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(value).replace(tzinfo=None)
    except Exception:
        return None


def _parse_kakao_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except Exception:
        return None


def _strip(html: str) -> str:
    import html as _h
    import re
    text = re.sub(r"<[^>]+>", " ", html or "")   # 태그 제거
    text = _h.unescape(text)                       # &nbsp; &amp; 등 엔티티 복원
    text = re.sub(r"https?://\S+", " ", text)      # URL 제거
    text = re.sub(r"\s+", " ", text)
    return text.strip()
