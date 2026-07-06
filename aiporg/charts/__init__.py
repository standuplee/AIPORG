"""차트 생성 (PRD 9항). 분석결과 -> PNG 파일.

matplotlib(한국어 폰트) + wordcloud + networkx 사용. 생성 함수는 모두
출력 경로를 반환하며, 실패 시 None 을 반환해 보고서가 계속 진행되도록 한다.
"""
from .render import ChartRenderer

__all__ = ["ChartRenderer"]
