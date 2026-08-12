"""키워드 조사 보고서 전용 레이아웃 상수와 헬퍼."""
from __future__ import annotations


def summary_labels() -> list[str]:
    return [
        "분석기간",
        "분석채널",
        "핵심 검색어",
        "긍정여론",
        "전월 대비",
    ]


def toc_items() -> list[str]:
    return [
        "제1장 분석 개요",
        "제2장 월간 주요 이슈 동향",
        "제3장 온라인 채널별 여론 동향",
        "제4장 감성 분석 - 긍·부정 여론 동향",
        "제5장 시사점 및 도정 운영 제언",
        "제6장 출처 및 참고자료",
    ]


def empty_state_text() -> str:
    return "수집 결과 없음"
