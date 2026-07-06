"""AIPORG - AI Public Opinion Report Generator.

온라인 여론 데이터를 수집·분석하여 공공기관 수준의 월간 여론분석
보고서를 자동 생성하는 시스템.

파이프라인: collect -> analyze -> (LLM narrative) -> report(DOCX/HTML/MD)
"""

__version__ = "1.0.0"
