"""블로그 수집기 (네이버/티스토리/브런치)."""
from __future__ import annotations

import hashlib
import os
from datetime import date

from ..models import Channel, Document
from .base import BaseCollector


class NaverBlogCollector(BaseCollector):
    name = "naver_blog"
    channel = Channel.BLOG

    def collect(self, keywords: list[str], start: date, end: date) -> list[Document]:
        cid = os.environ.get("NAVER_CLIENT_ID")
        secret = os.environ.get("NAVER_CLIENT_SECRET")
        if not (cid and secret):
            return []
        import re
        import requests

        docs: list[Document] = []
        headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}
        clean = lambda s: re.sub(r"<[^>]+>", "", s or "")
        for kw in keywords[:3]:
            stop = False
            for page in range(1, 1001, 100):
                r = requests.get(
                    "https://openapi.naver.com/v1/search/blog.json",
                    params={"query": kw, "display": 100, "start": page, "sort": "date"},
                    headers=headers, timeout=self.timeout,
                )
                if r.status_code != 200:
                    break
                items = r.json().get("items", [])
                if not items:
                    break
                for item in items:
                    pub = _parse_postdate(item.get("postdate"))
                    if pub:
                        if pub.date() > end:
                            continue
                        if pub.date() < start:
                            stop = True
                            continue
                    link = item.get("link", "")
                    docs.append(Document(
                        doc_id=hashlib.sha1(link.encode()).hexdigest()[:16],
                        channel=self.channel, title=clean(item.get("title", "")),
                        body=clean(item.get("description", "")), url=link,
                        published_at=pub, author=item.get("bloggername"),
                        matched_keywords=[kw],
                    ))
                if stop or len(items) < 100:
                    break
        return docs


def _parse_postdate(value):
    """네이버 블로그 postdate (yyyyMMdd) -> datetime. 실패 시 None."""
    if not value:
        return None
    try:
        from datetime import datetime
        return datetime.strptime(str(value), "%Y%m%d")
    except Exception:
        return None
