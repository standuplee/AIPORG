"""YouTubeService — 수집→분석→요약→Report 오케스트레이션 (+캐싱).

30일 캐시: 동일 keyword+기간으로 수집한 원자료는 재호출하지 않음(force=True 예외).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from . import config as C
from .analyzer import issues as issue_mod
from .analyzer import keywords as kw_mod
from .analyzer import sentiment as sent_mod
from .analyzer import summarize as sum_mod
from .analyzer import topics as topic_mod
from .analyzer import trends as trend_mod
from .collector import ApiClient, VideoCollector, YouTubeApiClient
from .comments import CommentCollector
from .report import build_report
from .repository import YouTubeRepository
from .schema import Comment, Video, YouTubeReport

log = logging.getLogger(__name__)


class YouTubeService:
    """수집·분석 파이프라인. client 를 주입하면(Mock 포함) API 없이도 동작."""

    def __init__(self, cfg: C.YouTubeConfig, client: Optional[ApiClient] = None,
                 repo: Optional[YouTubeRepository] = None) -> None:
        self.cfg = cfg
        self.repo = repo or YouTubeRepository(cfg.db_path)
        self.client = client or self._default_client()

    @staticmethod
    def _default_client() -> Optional[ApiClient]:
        key = os.environ.get("YOUTUBE_API_KEY")
        return YouTubeApiClient(key) if key else None

    # ------------------------------------------------------------------ #
    def _run_cache_key(self) -> str:
        kws = "+".join(self.cfg.limited_keywords())
        return self.cfg.cache_key(kws)

    def collect(self) -> tuple[list[Video], list[Comment]]:
        """영상·댓글 수집 (캐시 우선)."""
        cache_key = self._run_cache_key()
        if not self.cfg.force:
            cached = self.repo.cache_get(cache_key, C.CACHE_TTL_DAYS)
            if cached:
                log.info("캐시 사용: %s", cache_key)
                return ([Video(**v) for v in cached["videos"]],
                        [Comment(**c) for c in cached["comments"]])

        if self.client is None:
            log.warning("YOUTUBE_API_KEY 없음 & Mock 미주입 → 빈 수집")
            return [], []

        videos = VideoCollector(self.client).collect(self.cfg)
        comments = CommentCollector(self.client).collect(videos)
        self.repo.cache_put(cache_key, {
            "videos": [v.model_dump() for v in videos],
            "comments": [c.model_dump() for c in comments]})
        return videos, comments

    def analyze(self, videos: list[Video], comments: list[Comment]) -> YouTubeReport:
        # 감성 라벨링 (영상=제목+설명, 댓글=본문)
        for v in videos:
            v.sentiment = sent_mod.classify(f"{v.title} {v.description}")
            v.topic = topic_mod.classify_video(v)
        for c in comments:
            c.sentiment = sent_mod.classify(c.text)

        # 채널 감성: 댓글 우선(이용자 반응), 없으면 영상
        base_labels = [c.sentiment for c in comments] or [v.sentiment for v in videos]
        channel_sent = sent_mod.aggregate([x for x in base_labels if x])

        # 이슈·키워드는 영상 제목·설명(주제어) 기준으로 추출한다.
        # (댓글은 감성 산출에만 사용 — 감성어가 이슈 키워드를 잠식하지 않도록)
        video_texts = [f"{v.title} {v.description}" for v in videos]
        keywords = kw_mod.top_keywords(video_texts, top_n=20)
        topics = topic_mod.distribution(videos, top_n=6)
        issues = issue_mod.compute(videos, comments, keywords, top_n=10)
        trends = trend_mod.detect(videos, comments, issues)
        ai_summary = sum_mod.summarize(videos, comments, keywords, channel_sent,
                                       issues, model=self.cfg.gemini_model)

        report = build_report(self.cfg, videos, comments, keywords, topics,
                              issues, trends, channel_sent, ai_summary)
        return report

    def run(self) -> YouTubeReport:
        """전체 실행: 수집 → 저장 → 분석 → Report 저장."""
        videos, comments = self.collect()
        self.repo.save_videos(videos)
        self.repo.save_comments(comments)
        report = self.analyze(videos, comments)
        self.repo.save_report(self.cfg.period_start.isoformat(),
                              self.cfg.period_end.isoformat(),
                              report.model_dump_json())
        log.info("YouTube 분석 완료: 영상 %d / 댓글 %d / 이슈 %d",
                 len(videos), len(comments), len(report.notable_trends))
        return report
