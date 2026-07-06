"""댓글 수집기 (commentThreads.list).

스펙: 댓글 5개 이상 영상 중 조회수 상위 15개 대상, 영상당 최대 20개,
order=relevance. 작성자 이름/채널URL/프로필은 저장하지 않고 author_hash 만 보관.
"""
from __future__ import annotations

import logging

from . import config as C
from .collector import ApiClient
from .schema import Comment, Video, author_hash

log = logging.getLogger(__name__)


class CommentCollector:
    def __init__(self, client: ApiClient) -> None:
        self.client = client

    def collect(self, videos: list[Video]) -> list[Comment]:
        targets = [v for v in videos if v.comment_count >= C.MIN_COMMENTS_FOR_COLLECT]
        targets.sort(key=lambda v: v.view_count, reverse=True)
        targets = targets[:C.COMMENT_TARGET_VIDEOS]

        comments: list[Comment] = []
        for v in targets:
            try:
                items = self.client.comment_threads(v.video_id, C.MAX_COMMENTS_PER_VIDEO)
            except Exception as exc:  # noqa: BLE001
                log.warning("comment 수집 실패(%s): %s", v.video_id, exc)
                continue
            for it in items[:C.MAX_COMMENTS_PER_VIDEO]:
                comments.append(self._to_comment(it, v.video_id))
        return comments

    @staticmethod
    def _to_comment(item: dict, video_id: str) -> Comment:
        top = item.get("snippet", {}).get("topLevelComment", {})
        sn = top.get("snippet", {})
        return Comment(
            comment_id=top.get("id", item.get("id", "")),
            video_id=video_id,
            text=sn.get("textDisplay", "")[:500],
            published_at=sn.get("publishedAt"),
            like_count=int(sn.get("likeCount", 0) or 0),
            # 작성자 표시명은 해시만 저장(원문·URL·프로필 미저장)
            author_hash=author_hash(sn.get("authorDisplayName")),
        )
