"""YouTube 서브시스템 pytest (Mock 기반, API 키 불필요)."""
from __future__ import annotations

import os
import tempfile

import pytest

from aiporg.youtube import config as C
from aiporg.youtube.analyzer import issues, keywords, sentiment, topics
from aiporg.youtube.collector import VideoCollector
from aiporg.youtube.comments import CommentCollector
from aiporg.youtube.mock_data import MockApiClient
from aiporg.youtube.repository import YouTubeRepository
from aiporg.youtube.schema import Comment, Video, author_hash
from aiporg.youtube.service import YouTubeService


@pytest.fixture()
def cfg() -> C.YouTubeConfig:
    db = os.path.join(tempfile.mkdtemp(), "yt_test.db")
    return C.YouTubeConfig(db_path=db)


@pytest.fixture()
def client() -> MockApiClient:
    return MockApiClient()


# --- 수집/Quota ------------------------------------------------------------- #
def test_video_collect_dedup_and_cap(cfg, client):
    videos = VideoCollector(client).collect(cfg)
    ids = [v.video_id for v in videos]
    assert len(ids) == len(set(ids)), "중복 영상이 존재하면 안 됨"
    assert len(videos) <= C.MAX_TOTAL_VIDEOS
    assert all(v.url.startswith("https://www.youtube.com/watch?v=") for v in videos)


def test_keyword_limit():
    cfg = C.YouTubeConfig(keywords=[f"kw{i}" for i in range(20)])
    assert len(cfg.limited_keywords()) == C.MAX_KEYWORDS


def test_comment_rules(cfg, client):
    videos = VideoCollector(client).collect(cfg)
    comments = CommentCollector(client).collect(videos)
    # 영상당 최대 20개
    per_video: dict[str, int] = {}
    for c in comments:
        per_video[c.video_id] = per_video.get(c.video_id, 0) + 1
    assert all(n <= C.MAX_COMMENTS_PER_VIDEO for n in per_video.values())
    # 댓글 수집 대상 영상 수 ≤ 15
    assert len(per_video) <= C.COMMENT_TARGET_VIDEOS
    # 댓글 5개 미만 영상은 제외 (vid012=comments 3)
    assert "vid012" not in per_video


def test_privacy_no_author_name(cfg, client):
    videos = VideoCollector(client).collect(cfg)
    comments = CommentCollector(client).collect(videos)
    assert comments, "댓글이 수집되어야 함"
    for c in comments:
        assert c.author_hash and len(c.author_hash) == 16
        # 원문 작성자명(user_0 등)이 저장되면 안 됨
        assert "user_" not in c.author_hash
    # 해시는 단방향 (동일 입력 동일 출력)
    assert author_hash("홍길동") == author_hash("홍길동")
    assert author_hash("홍길동") != author_hash("김철수")


# --- 분석 ------------------------------------------------------------------- #
def test_keyword_extraction():
    texts = ["충남 반도체 투자 유치 성과", "박수현 도지사 반도체 산업 육성",
             "반도체 일자리 기대"]
    ks = keywords.top_keywords(texts, top_n=10)
    kws = [k.keyword for k in ks]
    assert "반도체" in kws
    assert all(k.frequency >= 1 for k in ks)


def test_sentiment_classify_and_aggregate():
    assert sentiment.classify("정말 좋고 응원합니다 기대됩니다") == "긍정"
    assert sentiment.classify("최악이다 실망 비판 우려") == "부정"
    agg = sentiment.aggregate(["긍정", "긍정", "부정", "중립"])
    assert agg.total_analyzed == 4
    assert abs(agg.positive - 50.0) < 0.01


def test_topic_categories_valid(cfg, client):
    videos = VideoCollector(client).collect(cfg)
    valid = set(topics.valid_categories())
    for v in videos:
        assert topics.classify_video(v) in valid


def test_issue_score_top10(cfg, client):
    videos = VideoCollector(client).collect(cfg)
    comments = CommentCollector(client).collect(videos)
    texts = [f"{v.title} {v.description}" for v in videos]
    ks = keywords.top_keywords(texts, 20)
    result = issues.compute(videos, comments, ks, top_n=10)
    assert len(result) <= 10
    # 점수 내림차순 + rank 부여
    scores = [i.score for i in result]
    assert scores == sorted(scores, reverse=True)
    assert [i.rank for i in result] == list(range(1, len(result) + 1))


# --- Report / 문체 ---------------------------------------------------------- #
def test_full_run_report_shape(cfg, client):
    report = YouTubeService(cfg, client=client).run()
    assert report.source == "youtube"
    assert report.youtube_overview.video_count > 0
    assert report.channel_sentiment.total_analyzed > 0
    assert report.top_keywords and report.top_topics
    assert report.top_videos and report.governor_evaluation
    assert report.recommendations


def test_report_style_youtube_scoped(cfg, client):
    report = YouTubeService(cfg, client=client).run()
    blob = report.model_dump_json()
    # 유튜브 한정 표현 사용, 전체 여론 일반화 금지
    assert "도민은" not in blob
    assert any(p in blob for p in ("유튜브 이용자", "영상 댓글", "유튜브 채널"))
    # 개조식 종결
    assert any(e in blob for e in ("로 나타남", "로 분석됨", "로 집계됨", "판단됨"))


def test_governor_eval_note_scoped(cfg, client):
    report = YouTubeService(cfg, client=client).run()
    assert "전체 여론을" in report.governor_evaluation.note


# --- 캐시 / Repository ------------------------------------------------------ #
def test_cache_reuse(cfg, client):
    svc = YouTubeService(cfg, client=client)
    v1, c1 = svc.collect()
    # 두 번째 호출은 캐시 사용(동일 결과)
    v2, c2 = svc.collect()
    assert len(v1) == len(v2) and len(c1) == len(c2)


def test_force_bypasses_cache(cfg, client):
    YouTubeService(cfg, client=client).collect()
    cfg.force = True
    v, _ = YouTubeService(cfg, client=client).collect()
    assert v, "force 재수집 결과가 있어야 함"


def test_repository_roundtrip(cfg):
    repo = YouTubeRepository(cfg.db_path)
    repo.save_videos([Video(video_id="x1", title="t", view_count=10)])
    repo.save_comments([Comment(comment_id="c1", video_id="x1", text="hi",
                                author_hash="abc")])
    assert repo.counts() == {"videos": 1, "comments": 1}
