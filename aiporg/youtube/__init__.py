"""YouTube 여론 수집·분석 서브시스템.

YouTube Data API v3 를 하나의 데이터 소스(Collector)로 사용하여 영상·댓글을
수집하고, 키워드/감성/이슈/특이동향/AI요약을 산출해 공공기관 문체의 Report
JSON 을 생성한다. 무료 Quota 내 동작을 원칙으로 한다.

계층:
    collector  -> 영상 검색·조회 (search.list, videos.list)
    comments   -> 댓글 수집 (commentThreads.list)
    repository -> SQLite 저장 (videos/comments/summary/cache)
    analyzer   -> 키워드/감성/토픽/이슈/트렌드/요약
    service    -> 수집→분석→요약 오케스트레이션 (+캐싱)
    report     -> Report JSON 생성 (유튜브 채널 한정 문체)
    api        -> FastAPI 라우터
"""
from .config import YouTubeConfig
from .service import YouTubeService

__all__ = ["YouTubeConfig", "YouTubeService"]
