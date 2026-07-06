"""YouTube Data API v3 클라이언트 및 영상 수집기 (Quota 절약).

수집 흐름(스펙 준수):
  keyword(≤9) → search.list(video, maxResults 10) → 영상 후보(≤60)
  → 중복 제거 → videos.list(part=snippet,statistics, 50개 batch)
"""
from __future__ import annotations

import logging
from typing import Optional, Protocol

from . import config as C
from .schema import Video

log = logging.getLogger(__name__)


class ApiClient(Protocol):
    """YouTube API 호출 추상화 (테스트 시 Mock 주입)."""

    def search(self, keyword: str, cfg: C.YouTubeConfig) -> list[str]: ...
    def videos(self, video_ids: list[str]) -> list[dict]: ...
    def comment_threads(self, video_id: str, max_results: int) -> list[dict]: ...


class YouTubeApiClient:
    """실제 HTTP 클라이언트 (YOUTUBE_API_KEY 필요)."""

    SEARCH = "https://www.googleapis.com/youtube/v3/search"
    VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
    COMMENTS = "https://www.googleapis.com/youtube/v3/commentThreads"

    def __init__(self, api_key: str, timeout: int = 15) -> None:
        self.api_key = api_key
        self.timeout = timeout

    def search(self, keyword: str, cfg: C.YouTubeConfig) -> list[str]:
        import requests

        resp = requests.get(self.SEARCH, timeout=self.timeout, params={
            "part": "snippet", "type": "video", "q": keyword,
            "maxResults": C.VIDEOS_PER_KEYWORD, "regionCode": cfg.region_code,
            "relevanceLanguage": cfg.relevance_language, "order": "relevance",
            "publishedAfter": cfg.published_after,
            "publishedBefore": cfg.published_before, "key": self.api_key,
        })
        resp.raise_for_status()
        return [it["id"]["videoId"] for it in resp.json().get("items", [])
                if it.get("id", {}).get("videoId")]

    def videos(self, video_ids: list[str]) -> list[dict]:
        import requests

        out: list[dict] = []
        for i in range(0, len(video_ids), C.VIDEOS_BATCH_SIZE):
            batch = video_ids[i:i + C.VIDEOS_BATCH_SIZE]
            resp = requests.get(self.VIDEOS, timeout=self.timeout, params={
                "part": "snippet,statistics", "id": ",".join(batch),
                "key": self.api_key})
            resp.raise_for_status()
            out.extend(resp.json().get("items", []))
        return out

    def comment_threads(self, video_id: str, max_results: int) -> list[dict]:
        import requests

        resp = requests.get(self.COMMENTS, timeout=self.timeout, params={
            "part": "snippet", "videoId": video_id, "maxResults": max_results,
            "order": "relevance", "textFormat": "plainText", "key": self.api_key})
        resp.raise_for_status()
        return resp.json().get("items", [])


def _match_keywords(text: str, keywords: list[str]) -> list[str]:
    return [k for k in keywords if k in text]


class VideoCollector:
    """영상 검색·상세조회 담당."""

    def __init__(self, client: ApiClient) -> None:
        self.client = client

    def collect(self, cfg: C.YouTubeConfig) -> list[Video]:
        keywords = cfg.limited_keywords()
        id_to_kw: dict[str, set[str]] = {}
        for kw in keywords:
            try:
                vids = self.client.search(kw, cfg)
            except Exception as exc:  # noqa: BLE001
                log.warning("search 실패(%s): %s", kw, exc)
                continue
            for vid in vids[:C.VIDEOS_PER_KEYWORD]:
                id_to_kw.setdefault(vid, set()).add(kw)
            if len(id_to_kw) >= C.MAX_TOTAL_VIDEOS:
                break

        video_ids = list(id_to_kw.keys())[:C.MAX_TOTAL_VIDEOS]   # 중복제거 + 상한
        if not video_ids:
            return []
        items = self.client.videos(video_ids)
        return [self._to_video(it, cfg.keywords, id_to_kw) for it in items]

    @staticmethod
    def _to_video(item: dict, keywords: list[str],
                  id_to_kw: dict[str, set[str]]) -> Video:
        sn = item.get("snippet", {})
        st = item.get("statistics", {})
        vid = item.get("id", "")
        text = f"{sn.get('title','')} {sn.get('description','')}"
        matched = sorted(set(_match_keywords(text, keywords)) | id_to_kw.get(vid, set()))
        return Video(
            video_id=vid, title=sn.get("title", ""),
            description=sn.get("description", "")[:500],
            channel_title=sn.get("channelTitle", ""),
            published_at=sn.get("publishedAt"),
            view_count=int(st.get("viewCount", 0) or 0),
            like_count=int(st.get("likeCount", 0) or 0),
            comment_count=int(st.get("commentCount", 0) or 0),
            url=f"https://www.youtube.com/watch?v={vid}",
            matched_keywords=matched,
        )
