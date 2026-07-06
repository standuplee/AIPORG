"""공공기관 문체 프롬프트 설계 (본 시스템 품질의 핵심).

원본 리포트(충남 여론분석컨설팅 보고서)의 문체를 재현하기 위한
스타일 가이드와 절(section)별 프롬프트 빌더. LLM provider(gemini/openai)
사용 시 이 프롬프트가 그대로 주입된다.

핵심 설계 원칙 (PRD 12항 품질목표 반영):
  1) 수치 정확성  : 프롬프트에 '수집 데이터에 있는 수치만 사용, 임의 생성 금지'를 강제.
  2) 출처 추적성  : 각 이슈/문장은 evidence(원문 링크)에 근거.
  3) 문체 일관성  : 개조식 종결(-됨/-함/-임), 3인칭 관찰자 시점, 건조한 분석체.
  4) 재현성       : temperature 낮게, 사실 나열 순서를 데이터 순서에 고정.
"""
from __future__ import annotations

import json

# --------------------------------------------------------------------------- #
# 시스템 프롬프트 (문체 헌장)
# --------------------------------------------------------------------------- #
STYLE_GUIDE = """당신은 대한민국 공공기관(지방자치단체) 여론분석 보고서를 집필하는
전문 애널리스트다. 아래 문체 규칙을 반드시 준수하여 보고서 문장을 작성하라.

[문체 규칙]
1. 종결어미는 개조식 '음슴체'를 사용한다: '~로 분석됨', '~로 나타남', '~가 필요함',
   '~진행함'. 평서형 '~습니다/~한다/~였다'는 사용하지 않는다.
2. 3인칭 관찰자 시점의 건조하고 객관적인 분석체를 유지한다. 감탄·수사·홍보성
   표현('놀라운', '획기적인' 등)을 배제한다.
3. 한 문장에 하나의 사실을 담되, 근거 수치를 함께 제시한다.
   예) '총 언급량은 38,724건으로 전월 대비 12.4% 증가한 것으로 분석됨'
4. 수치는 천단위 콤마와 단위(건/%)를 명확히 표기한다.
5. 나열은 '~, ~, ~ 순으로 나타남' 형식으로 정리한다.
6. 기관·직위·인물명은 공식 명칭을 사용한다.
7. 문단은 2~3문장 내외로 간결하게 구성한다.

[사실성 규칙 — 매우 중요]
8. 제공된 DATA(JSON)에 존재하는 수치·항목만 사용한다. DATA에 없는 통계·비율·
   건수를 임의로 만들어내지 않는다.
9. 인물명은 DATA에 명시된 대상만 사용한다.
10. 불확실하거나 데이터에 없는 내용은 서술하지 않는다.

출력은 보고서 본문 문장만 반환하며, 머리말·설명·마크다운 기호를 포함하지 않는다.
"""


# --------------------------------------------------------------------------- #
# 절별 프롬프트 빌더
# 각 빌더는 (system, user) 튜플을 반환. user 프롬프트에는 grounded DATA 를 첨부.
# --------------------------------------------------------------------------- #
def _data_block(payload: dict) -> str:
    return "```DATA\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"


def volume_overview(data: dict) -> tuple[str, str]:
    user = f"""다음 DATA를 근거로 '3월 온라인 언급량 개요' 문단을 작성하라.
- 첫 문장: 총 언급량, 전월 대비 증감률, 대상별 언급량(subject_volumes), 긍정여론 비율 포함.
- 둘째 문장: 채널별 언급 비중(channel_share) 상위 3개를 '~ 순으로 나타남'으로 서술.
{_data_block(data)}"""
    return STYLE_GUIDE, user


def top_issues_overview(data: dict) -> tuple[str, str]:
    user = f"""다음 DATA(top_issues)를 근거로 '핵심 이슈 TOP10 개요' 문단을 작성하라.
- 이슈들의 카테고리 분포를 언급하고, 1위·2위 이슈를 건수와 함께 제시.
- 긍정 반응 이슈들과 부정 반응 이슈를 구분하여 서술.
{_data_block(data)}"""
    return STYLE_GUIDE, user


def channel_sentiment(data: dict) -> tuple[str, str]:
    user = f"""다음 DATA(channel_sentiments, overall_sentiment)를 근거로
'채널별 온라인 여론 감성 분석' 문단을 작성하라.
- 긍정 여론이 높은 채널과 부정 여론이 높은 채널을 구분.
- 채널별 여론 특징(feature_text, feature_volume)을 건수와 함께 서술.
- 전체 종합 감성(긍정/중립/부정 %)을 제시하고 부정 여론의 원인을 요약.
{_data_block(data)}"""
    return STYLE_GUIDE, user


def related_keywords(data: dict) -> tuple[str, str]:
    user = f"""다음 DATA(related_keywords, positive_keywords, negative_keywords)를 근거로
'주요 연관 키워드' 문단을 작성하라.
- 상위 연관 키워드 3개를 건수와 함께 '~ 순으로 높게 나타남'으로 서술.
- 긍정적 반응 키워드와 부정적 반응 키워드를 구분하여 나열.
{_data_block(data)}"""
    return STYLE_GUIDE, user


def core_keywords(data: dict) -> tuple[str, str]:
    user = f"""다음 DATA(core_keywords)를 근거로 '핵심 키워드 상세 분석' 문단을 작성하라.
- 각 핵심 이슈의 여론 동향을 analysis 내용을 바탕으로 2~4문장으로 종합.
{_data_block(data)}"""
    return STYLE_GUIDE, user


def job_evaluation(data: dict) -> tuple[str, str]:
    user = f"""다음 DATA(job_evaluation)를 근거로 '도지사 직무수행 평가' 문단을 작성하라.
- 첫 문장: 평가 대상, 긍정의견 %, 부정의견 % 제시.
- 긍정평가 주요 요인(positive_reasons)을 나열.
- 부정평가 주요 요인(negative_reasons)을 나열.
{_data_block(data)}"""
    return STYLE_GUIDE, user


def implications(data: dict) -> tuple[str, str]:
    user = f"""다음 DATA(implications)를 근거로 '종합 시사점 및 제언' 마무리 문단을 작성하라.
- 각 시사점의 headline 을 종합하여 도 차원에서 필요한 대응 방향을 2~3문장으로 정리.
{_data_block(data)}"""
    return STYLE_GUIDE, user
