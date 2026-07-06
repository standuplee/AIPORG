"""AI 분석 파이프라인 (PRD 7항).

중복제거 -> 키워드추출 -> NER -> 토픽군집화 -> 감성분석 -> 언급량 ->
연관키워드 -> 트렌드 -> 요약 순으로 Document 집합을 AnalysisResult 로 변환.
"""
from .pipeline import AnalysisPipeline

__all__ = ["AnalysisPipeline"]
