"""한국어 텍스트 전처리 유틸 (형태소 분석기 의존 없이 동작).

konlpy(Mecab/Okt) 가 설치되어 있으면 명사 추출에 사용하고, 없으면
정규식 기반 토크나이저로 degrade 한다.
"""
from __future__ import annotations

import re

# 조사/불용어 최소 집합
STOPWORDS = {
    "그리고", "그러나", "또한", "관련", "대한", "위한", "통해", "대해", "에서",
    "으로", "하는", "했다", "한다", "있다", "없다", "이다", "되는", "부터",
    "까지", "및", "등", "것", "수", "이", "그", "저", "때", "년", "월", "일",
    "기자", "뉴스", "제공", "무단", "전재", "재배포", "금지", "사진",
}

# RSS/HTML 잔여 boilerplate (구글 뉴스 요약 등에 섞여 들어오는 영문 토큰)
BOILERPLATE = {
    "nbsp", "font", "href", "http", "https", "www", "com", "co", "kr", "html",
    "target", "blank", "span", "div", "style", "color", "google", "news", "amp",
    "quot", "rss", "utm", "src", "img", "li", "ul", "br", "nofollow", "rel",
}

_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")


def _keep(w: str) -> bool:
    lw = w.lower()
    if lw in BOILERPLATE or w in STOPWORDS:
        return False
    # 의미 없는 순수 숫자 토큰 제외
    if w.isdigit():
        return False
    return len(w) > 1

_okt = None


def _get_okt():
    global _okt
    if _okt is None:
        try:
            from konlpy.tag import Okt
            _okt = Okt()
        except Exception:
            _okt = False
    return _okt


def tokenize(text: str) -> list[str]:
    """단어 토큰 리스트. 형태소 분석기 있으면 명사 우선."""
    okt = _get_okt()
    if okt:
        try:
            return [w for w in okt.nouns(text) if _keep(w)]
        except Exception:
            pass
    return [w for w in _TOKEN_RE.findall(text) if _keep(w)]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
