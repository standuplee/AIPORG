"""SNS 수집기 (X / 유튜브 / 인스타그램).

각 플랫폼은 공식 API 토큰을 요구한다. 토큰이 설정되면 동작하도록
연동 지점을 명시하고, 없으면 빈 결과로 degrade 한다. (PRD 5항 '가능한 범위')
"""
from __future__ import annotations

import os
from datetime import date

from ..models import Channel, Document
from .base import BaseCollector


class XCollector(BaseCollector):
    name = "x"
    channel = Channel.X

    def collect(self, keywords: list[str], start: date, end: date) -> list[Document]:
        token = os.environ.get("X_BEARER_TOKEN")
        if not token:
            return []
        # TODO: X API v2 recent search 연동 (query = keywords, since/until = 기간)
        return []


class YouTubeCollector(BaseCollector):
    name = "youtube"
    channel = Channel.YOUTUBE

    def collect(self, keywords: list[str], start: date, end: date) -> list[Document]:
        key = os.environ.get("YOUTUBE_API_KEY")
        if not key:
            return []
        import requests

        docs: list[Document] = []
        for kw in keywords[:2]:
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet", "q": kw, "type": "video", "maxResults": 50,
                    "order": "relevance", "regionCode": "KR", "key": key,
                    "publishedAfter": f"{start.isoformat()}T00:00:00Z",
                    "publishedBefore": f"{end.isoformat()}T23:59:59Z",
                },
                timeout=self.timeout,
            )
            r.raise_for_status()
            for it in r.json().get("items", []):
                vid = it["id"].get("videoId", "")
                sn = it["snippet"]
                docs.append(Document(
                    doc_id=vid or sn["title"][:16], channel=self.channel,
                    title=sn.get("title", ""), body=sn.get("description", ""),
                    url=f"https://youtu.be/{vid}", author=sn.get("channelTitle"),
                    matched_keywords=[kw],
                ))
        return docs


class InstagramCollector(BaseCollector):
    name = "instagram"
    channel = Channel.INSTAGRAM

    def collect(self, keywords: list[str], start: date, end: date) -> list[Document]:
        # 인스타그램 그래프 API 는 비즈니스 계정/해시태그 권한 필요.
        if not os.environ.get("IG_ACCESS_TOKEN"):
            return []
        return []
