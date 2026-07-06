"""충남 2026-03 분석결과 fixture 생성기.

원본 리포트(충남202603여론조사분석리포트)의 수치를 그대로 인코딩하되,
인물 키워드 '김태흠' -> '박수현' 전면 치환한다. 라이브 수집 파이프라인이
산출할 AnalysisResult 와 동일한 구조이므로, 실데이터 연동 시 이 파일만
파이프라인 출력으로 대체하면 된다.

실행: python -m scripts.build_chungnam_fixture
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiporg.models import (  # noqa: E402
    AnalysisResult, Channel, ChannelSentiment, CoreKeyword, Implication,
    Issue, JobEvaluation, KeywordStat, Sentiment, SpecialTrend, _encode,
)

LEADER = "박수현"   # 원본 '김태흠' 치환


def _daily_volume(total: int, days: int = 30, month: int = 6, seed: int = 42) -> dict[str, int]:
    """전월 대비 증가 + 3주차(행정통합 무산) 급증을 반영한 결정론적 일별 추이."""
    import random

    rng = random.Random(seed)
    # 요일/주차 가중치: 3주차(day 15~21) 스파이크
    weights = []
    for d in range(1, days + 1):
        base = 1.0
        if 15 <= d <= 21:
            base = 1.8            # 행정통합 임시국회 무산 국면
        elif 8 <= d <= 14:
            base = 1.15
        wd = (d - 1) % 7
        if wd in (5, 6):
            base *= 0.75          # 주말 감소
        weights.append(base * (0.9 + rng.random() * 0.2))
    s = sum(weights)
    raw = [w / s * total for w in weights]
    ints = [int(round(x)) for x in raw]
    ints[-1] += total - sum(ints)   # 합계 보정
    return {f"2026-{month:02d}-{d:02d}": v for d, v in enumerate(ints, 1)}


def build() -> AnalysisResult:
    top_issues = [
        Issue(1, "행정", "대전·충남 행정통합 특별법 국회 처리 촉각", 8420, 34.0, Sentiment.NEUTRAL,
              ["https://search.naver.com/search.naver?where=news&query=대전충남+행정통합+특별법"],
              "행정통합 특별법의 국회 처리 지연으로 찬반 양측의 온라인 언급이 동시 확대됨"),
        Issue(2, "선거", "6·3 지방선거 충남도지사 공천 신청 결과 발표", 6180, 28.0, Sentiment.NEUTRAL,
              ["https://search.naver.com/search.naver?where=news&query=충남도지사+공천"],
              "6·3 지방선거를 앞두고 공천 신청 결과에 대한 관심이 집중됨"),
        Issue(3, "경제", "충남 AI 데이터센터 아산 음봉 2조5천억 투자 유치", 4920, 51.0, Sentiment.POSITIVE,
              ["https://search.naver.com/search.naver?where=news&query=아산+AI데이터센터+투자"],
              "대규모 투자 유치 발표로 지역 경제 기대감이 크게 상승함"),
        Issue(4, "산업", "천안·아산 K-AI 특화시범도시 공동 유치 추진", 3840, 22.0, Sentiment.POSITIVE,
              ["https://search.naver.com/search.naver?where=news&query=K-AI+특화도시+천안아산"],
              "AI 특화도시 공동 유치 추진으로 산업 기반 확충 기대가 형성됨"),
        Issue(5, "산업", "삼성전자 천안 반도체 패키징 증설 본격화", 3210, 18.0, Sentiment.POSITIVE,
              ["https://search.naver.com/search.naver?where=news&query=삼성전자+천안+반도체+패키징"],
              "반도체 패키징 증설로 지역 고용·투자 확대 전망이 부각됨"),
        Issue(6, "도정", "충남도 2026 주요업무계획 발표 및 도민 반응", 2780, 9.0, Sentiment.NEUTRAL,
              ["https://search.naver.com/search.naver?where=news&query=충남도+2026+주요업무계획"],
              "연간 주요업무계획 발표에 대한 도민의 관심과 평가가 이어짐"),
        Issue(7, "환경", "충남 화력발전소 탈석탄·탄소중립 전환 이슈", 2340, 5.0, Sentiment.MIXED,
              ["https://search.naver.com/search.naver?where=news&query=충남+화력발전+탈석탄"],
              "환경 기대와 지역경제 우려가 공존하며 찬반 여론이 혼재함"),
        Issue(8, "환경", "천안·아산 전력 인프라 부족 확충 시급 논란", 1860, 14.0, Sentiment.NEGATIVE,
              ["https://search.naver.com/search.naver?where=news&query=천안아산+전력인프라+부족"],
              "투자 확대에 따른 전력 인프라 부족 우려가 부정 여론으로 확산됨"),
        Issue(9, "복지", "충남 지역사회 통합돌봄 전국 시행 파급 효과", 1550, 8.0, Sentiment.POSITIVE,
              ["https://search.naver.com/search.naver?where=news&query=충남+통합돌봄+전국시행"],
              "통합돌봄 전국 시행의 선도 사례로 긍정적 평가가 형성됨"),
        Issue(10, "경제", "충남 소비자물가 6개월 연속 2%대 상승 우려", 1230, -2.0, Sentiment.NEGATIVE,
              ["https://search.naver.com/search.naver?where=news&query=충남+소비자물가+상승"],
              "물가 상승 지속에 대한 생활 부담 우려가 부정 여론으로 나타남"),
    ]

    # 실제 API 로 수집 가능한 채널만 사용 (X·인스타그램 제외)
    channel_sentiments = [
        ChannelSentiment(Channel.NEWS, 48.0, 22.0, 30.0, "도정 주요 정책·예산 성과 등", 17810),
        ChannelSentiment(Channel.COMMUNITY, 30.0, 15.0, 55.0, "지역 개발·일자리 기대 등", 9290),
        ChannelSentiment(Channel.BLOG, 60.0, 22.0, 18.0, "관광·맛집·생활정보 등", 6970),
        ChannelSentiment(Channel.YOUTUBE, 45.0, 25.0, 30.0, "정책 영상·현장 이슈 등", 3100),
        ChannelSentiment(Channel.RSS, 72.0, 24.0, 4.0, "도정 정책·보도자료 등", 1550),
    ]

    related = [
        ("대전충남통합", 8420, Sentiment.NEUTRAL), ("지방선거", 7810, Sentiment.NEUTRAL),
        ("AI데이터센터", 4920, Sentiment.POSITIVE), ("반도체", 3980, Sentiment.POSITIVE),
        ("행정통합반대", 3640, Sentiment.NEGATIVE), ("민생충남", 3120, Sentiment.POSITIVE),
        ("K-AI특화도시", 2870, Sentiment.POSITIVE), ("공천", 2540, Sentiment.NEUTRAL),
        ("삼성전자", 2310, Sentiment.POSITIVE), ("통합돌봄", 1980, Sentiment.POSITIVE),
        ("화력발전", 1760, Sentiment.NEGATIVE), ("전력인프라", 1540, Sentiment.NEGATIVE),
        ("탄소중립", 1420, Sentiment.MIXED), ("아산", 1350, Sentiment.POSITIVE),
        ("천안", 1280, Sentiment.POSITIVE), ("탈석탄", 1120, Sentiment.MIXED),
        ("소비자물가", 980, Sentiment.NEGATIVE), ("국비확보", 870, Sentiment.POSITIVE),
        ("주요업무계획", 760, Sentiment.NEUTRAL), (LEADER, 640, Sentiment.NEUTRAL),
    ]
    related_keywords = [
        KeywordStat(k, round(v / 8420, 4), v, s) for k, v, s in related
    ]

    special_trends = [
        SpecialTrend("행정통합 반대 커뮤니티 집중",
                     "3주차 대전·충남 행정통합 특별법 임시국회 처리 무산 "
                     "→ 커뮤니티·X(트위터) 중심 반대 여론 급증"),
        SpecialTrend("AI·반도체 투자 호재 긍정 확산",
                     "아산 AI데이터센터 2조 5천억 유치 발표 후 경제 기대감 SNS 확산"),
        SpecialTrend("지사 공천 미신청 관련 관심",
                     f"{LEADER} 지사 더불어민주당 공천 미신청 확인 → 재선 불출마 가능성 주목"),
        SpecialTrend("탄소 중립·탈석탄 정책 관심도 증가",
                     "국가 탄소중립 계획 구체화 시점과 맞물려 충남 화력 발전 대체 방안 지속 논의"),
    ]

    # 4대 핵심 이슈 카드 (그림 4-1). 이미지 레이아웃: 01/02 좌, 03/04 우.
    core_keywords = [
        CoreKeyword(
            "대전·충남 행정통합", 8420, Sentiment.MIXED, 34.0,
            "행정통합 특별법 3월 임시국회 처리 불발로 여론의 양극화가 심화되고 있음",
            top_issues[0].evidence,
            summary="행정통합 특별법 3월 임시국회 처리 불발 → 여론 양극화 심화",
            positive_point="통합 찬성: 경제규모 확대·광역 행정 효율화 기대 (X·뉴스 중심)",
            negative_point="통합 반대: 졸속 추진·지방선거 정치 이용 우려 (커뮤니티 집중)",
            keywords=["대전충남특별시", "행정통합", "주민투표", "선거", "졸속"]),
        CoreKeyword(
            "반도체·AI 산업 투자", 8130, Sentiment.POSITIVE, 40.0,
            "아산 AI 데이터센터 2.5조 유치, 천안 삼성 패키징 증설 호재로 기대감이 집중되고 있음",
            top_issues[2].evidence + top_issues[4].evidence,
            summary="아산 AI 데이터센터 2.5조 유치·천안 삼성 패키징 증설 호재",
            positive_point="일자리 창출·지역경제 활성화·미래산업 거점 기대감 집중",
            negative_point="수도권 반도체 메가클러스터 소외 우려·전력인프라 부족 지적",
            keywords=["AI데이터센터", "반도체패키징", "K-AI", "천안아산", "투자유치"]),
        CoreKeyword(
            "6·3 지방선거", 7810, Sentiment.NEUTRAL, 28.0,
            f"충남도지사 공천 신청 국면에서 {LEADER} 재선 행보에 주목한 일시적 관심도가 증가하였음",
            top_issues[1].evidence,
            summary=f"충남도지사 공천 신청 국면 → {LEADER} 재선 여부·경쟁 구도 주목",
            positive_point="여권 지지층 결집·도정 성과 기반 재선 기대 (지지층 호감)",
            negative_point="공천 갈등·네거티브 과열 비판 (일부 지지층 실망)",
            keywords=["지방선거", "충남지사", "공천", LEADER, "민선9기"]),
        CoreKeyword(
            "탄소중립·에너지 전환", 4460, Sentiment.MIXED, 9.0,
            "국가 탄소중립 계획 구체화 시점과 맞물려 충남 화력 발전 대체 논의가 지속되고 있음",
            top_issues[6].evidence,
            summary="국가 탄소중립 계획 구체화 시점, 충남 화력발전 대체 논의 지속",
            positive_point="2045년 탄소중립 목표·친환경 에너지 전환 정책 지지 여론",
            negative_point="탈석탄 이후 지역경제 일자리 타격·대체방안 부재 우려",
            keywords=["탄소중립", "화력발전", "탈석탄", "에너지전환", "보령", "당진"]),
    ]

    job_eval = JobEvaluation(
        subject=f"{LEADER} 충남지사",
        positive_pct=45.0,
        negative_pct=38.0,
        neutral_pct=17.0,
        positive_reasons=[
            "AI·반도체 투자 유치 성과 체감 (2.5조 유치)",
            "민생충남 도정 기조 및 소통 행보 긍정 평가",
            "충남 국비 12조 3223억 역대 최대 확보 성과",
        ],
        negative_reasons=[
            "행정통합 갈등·주민 의견 반영 부족 지적",
            "공천 미신청 리더십 불확실성 우려",
            "전력인프라 부족·탈석탄 대응 미흡 비판",
        ],
        highlight_region="충남",
        comparison={"전국평균": 50.0, "경남": 41.0, "대전": 43.0, "부산": 46.0,
                    "인천": 48.0, "충남": 45.0, "서울": 56.0, "경기": 58.0},
    )

    implications = [
        Implication(
            "대전·충남 행정 통합", "도민 소통 강화 시급",
            "행정통합 특별법 처리 연기로 반대 여론이 커뮤니티·X(트위터) 중심으로 급증, "
            "주민투표 요구와 졸속 추진 비판이 증가함에 따라 충남도 차원의 투명한 통합 정보 "
            "공개 및 도민 의견 수렴 채널 확대 필요",
            "온라인 소통채널 통합 설명회 / 도민 의견함 운영"),
        Implication(
            "AI·반도체 투자", "긍정 여론 지속 확산 필요",
            "아산 AI 데이터센터, 천안 반도체 패키징 증설 호재에 따른 긍정 여론이 SNS 전반 확산, "
            "전력인프라 부족 우려 동시 부각, 투자 성과 구체화·전력 대응 계획 공개로 신뢰도 제고 노력 필요",
            "AI 투자성과 정기 SNS 업데이트 / 전력인프라 계획 공표"),
        Implication(
            "지방선거 국면", "도정 성과 객관적 홍보 강화",
            "6·3 지방선거를 앞두고 도정 성과, 공약이행률에 대한 온라인 검색 및 언급량 증가에 따라 "
            "충남도 주요 사업 성과를 체계적으로 정리·공개해 도민의 합리적 평가 판단 지원",
            "민선 8기 성과 인포그래픽·카드뉴스 제작 및 배포"),
        Implication(
            "탄소중립·에너지 전환", "지역 경제 연계 로드맵 공유 필요",
            "탈석탄·탄소중립 이슈는 환경 기대와 경제 우려가 공존, 화력발전 폐지 이후 지역경제 지원·"
            "일자리 전환 계획을 구체적으로 제시함으로써 불만 여론 완화 및 긍정적 전환 유도",
            "탈석탄 이후 경제지원 로드맵 도민 공개 설명회"),
    ]

    return AnalysisResult(
        total_volume=38724,
        prev_change_pct=12.4,
        subject_volumes={"충남도정": 21380, "충남지사": 9842},
        subject_changes={"충남도정": 8.7, "충남지사": 18.3},
        positive_ratio=44.8,
        # 실제 수집 가능 채널만 (합 100%). X·인스타그램은 API 제약으로 제외.
        channel_share={"뉴스기사": 46.0, "커뮤니티": 24.0, "블로그": 18.0,
                       "유튜브": 8.0, "공공RSS": 4.0},
        daily_volume=_daily_volume(38724, days=30, month=6),
        top_issues=top_issues,
        channel_sentiments=channel_sentiments,
        overall_sentiment={"긍정": 44.8, "중립": 16.6, "부정": 38.6},
        related_keywords=related_keywords,
        positive_keywords=["AI데이터센터", "반도체", "민생충남", "K-AI특화도시", "통합돌봄"],
        negative_keywords=["행정통합반대", "화력발전", "전력인프라"],
        special_trends=special_trends,
        core_keywords=core_keywords,
        job_evaluation=job_eval,
        implications=implications,
        entities={
            "사람": [LEADER],
            "기관": ["충청남도", "충남도청", "충남도의회", "국회", "더불어민주당"],
            "지역": ["아산", "천안", "대전", "음봉"],
            "정책": ["행정통합", "탄소중립", "통합돌봄", "탈석탄"],
            "예산": ["2조5천억", "국비 12조 3223억"],
            "사업명": ["AI데이터센터", "K-AI특화도시", "반도체 패키징 증설"],
            "기업명": ["삼성전자"],
        },
    )


if __name__ == "__main__":
    import json

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiporg", "data", "chungnam_202606.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    result = build()
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(_encode(result), fh, ensure_ascii=False, indent=2)
    print(f"fixture 작성 완료: {out}")
    print(f"  총 언급량={result.total_volume:,} / 이슈={len(result.top_issues)} / "
          f"연관키워드={len(result.related_keywords)} / 대상={result.job_evaluation.subject}")
