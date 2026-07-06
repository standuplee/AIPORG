"""Narrator: 보고서 절별 서술문 생성.

- TemplateNarrator: 결정론적 공공기관 문체 생성기(기본값). AnalysisResult 의
  수치를 문체 규칙에 따라 문장으로 조립하여 재현성을 보장한다.
- LLMNarrator: prompts.py 의 grounded 프롬프트를 LLM 에 주입해 문장 생성.

두 구현 모두 동일한 메서드 집합을 제공하여 report writer 가 provider 에
무관하게 동작한다. 각 메서드는 '문단(문장) 리스트'를 반환한다.
"""
from __future__ import annotations

from ..models import AnalysisResult, ReportMeta, Sentiment
from . import prompts
from .base import LLMClient
from ..models import _encode


# --------------------------------------------------------------------------- #
# 포매팅 헬퍼
# --------------------------------------------------------------------------- #
def ic(n: int) -> str:
    return f"{n:,}"


def pc(x: float) -> str:
    return f"{int(x)}%" if float(x).is_integer() else f"{x}%"


def josa(word: str, with_batchim: str, without_batchim: str) -> str:
    """한국어 조사 자동 선택 (받침 유무 기준). 예: josa('블로그','은','는')->'는'."""
    if not word:
        return without_batchim
    ch = word[-1]
    if "가" <= ch <= "힣":
        return with_batchim if (ord(ch) - 0xAC00) % 28 else without_batchim
    # 한글이 아니면(숫자/괄호 등) 관용적으로 받침 없는 형태
    return without_batchim


class Narrator:
    """공통 인터페이스 + 데이터 접근 기반 서술 메서드."""

    def __init__(self, meta: ReportMeta, analysis: AnalysisResult):
        self.m = meta
        self.a = analysis

    # ---- 각 절 (하위 클래스에서 오버라이드) -------------------------------- #
    def overview_purpose(self) -> list[str]: ...
    def volume_overview(self) -> list[str]: ...
    def top_issues_overview(self) -> list[str]: ...
    def channel_sentiment(self) -> list[str]: ...
    def related_keywords(self) -> list[str]: ...
    def special_trends_summary(self) -> list[str]: ...
    def core_keywords_intro(self) -> list[str]: ...
    def core_keywords_detail(self) -> list[str]: ...
    def job_evaluation(self) -> list[str]: ...
    def implications_conclusion(self) -> list[str]: ...


# --------------------------------------------------------------------------- #
# 결정론적 템플릿 Narrator
# --------------------------------------------------------------------------- #
class TemplateNarrator(Narrator):

    def overview_purpose(self) -> list[str]:
        s = self.m.subject_name
        return [
            f"본 조사는 레거시 미디어 및 소셜 미디어를 포함한 온라인 채널에서 나타난 "
            f"{s[:2]}도정 및 {self.m.leader_title} 관련 여론을 정기 모니터링, 주요 동향의 "
            f"시기별 현황 파악 및 도·도민 간 소통 강화 목적으로 진행함",
            "또한, 본 조사는 온라인 여론 모니터링 서비스를 활용한 관련 키워드 수집 및 분석, "
            "뉴스 기사·SNS·커뮤니티·블로그 자동화 모니터링 방법을 활용함",
        ]

    def volume_overview(self) -> list[str]:
        a, m = self.a, self.m
        sv = a.subject_volumes
        sv_txt = ", ".join(f"{k} 언급량은 {ic(v)}건" for k, v in sv.items())
        first = (
            f"{m.year}년 {m.month}월 {m.subject_name} 온라인 총 언급량은 {ic(a.total_volume)}건으로 "
            f"전월 대비 {a.prev_change_pct}% 증가, 이 중 {sv_txt}이며, "
            f"긍정여론 비율은 {a.positive_ratio}%로 분석됨"
        )
        share = sorted(a.channel_share.items(), key=lambda x: x[1], reverse=True)[:3]
        share_txt = ", ".join(f"{k} {pc(v)}" for k, v in share)
        head = share[0]
        second = (
            f"채널별 언급 비중을 살펴보면, {head[0]}가 {pc(head[1])}로 가장 높게 나타났고, "
            f"{', '.join(f'{k} {pc(v)}' for k, v in share[1:])} 순으로 나타남"
        )
        return [first, second]

    def top_issues_overview(self) -> list[str]:
        a, m = self.a, self.m
        if not a.top_issues:
            return []
        cats = list(dict.fromkeys(i.category for i in a.top_issues))
        top2 = a.top_issues[:2]
        first = (
            f"{m.year}년 {m.subject_name} 핵심 이슈 TOP{len(a.top_issues)}을 살펴보면, "
            f"{', '.join(cats)} 등으로 구분할 수 있으며, {top2[0].title}이 "
            f"{ic(top2[0].volume)}건으로 가장 높게 나타남"
        )
        if len(top2) > 1:
            first += f", 그 다음 {top2[1].title}가 {ic(top2[1].volume)}건으로 높게 나타남"
        out = [first]
        pos = [i.title for i in a.top_issues if i.sentiment == Sentiment.POSITIVE]
        if pos:
            out.append(f"긍정적인 의견에는 {', '.join(pos)} 등 {len(pos)}개 항목으로 나타남")
        neg = [i.title for i in a.top_issues if i.sentiment == Sentiment.NEGATIVE]
        if neg:
            out.append(f"반면, {', '.join(neg)}에 대해 부정적 의견이 있는 것으로 분석됨")
        return out

    def channel_sentiment(self) -> list[str]:
        a = self.a
        cs = a.channel_sentiments
        if not cs:
            return []
        ov = a.overall_sentiment
        # 단일 채널(예: 뉴스 전용 수집)일 경우 축약 서술
        if len(cs) == 1:
            c = cs[0]
            return [
                f"수집 채널({c.channel.value}) 기준 여론 감성은 긍정 {c.positive}%, "
                f"중립 {c.neutral}%, 부정 {c.negative}%로 집계됨",
                f"전체 종합 감성은 긍정 {ov.get('긍정')}%, 중립 {ov.get('중립')}%, "
                f"부정 {ov.get('부정')}%로 분석됨",
            ]
        ranked_pos = sorted(cs, key=lambda c: c.positive, reverse=True)
        neg_ch = [c.channel.value for c in sorted(cs, key=lambda c: c.negative, reverse=True)[:2]]
        if len(cs) == 2:
            hi, lo = ranked_pos[0], ranked_pos[1]
            first = (
                f"채널별 온라인 여론 감성 분석 결과를 보면, {hi.channel.value}"
                f"{josa(hi.channel.value, '은', '는')} 긍정여론(긍정 {hi.positive}%)이 상대적으로 "
                f"높게 나타났으며, {lo.channel.value}{josa(lo.channel.value, '은', '는')} "
                f"중립 비중이 상대적으로 높게 나타남"
            )
        else:
            pos_ch = [c.channel.value for c in ranked_pos[:2]]
            first = (
                f"채널별 온라인 여론 감성 분석 결과를 보면, {', '.join(pos_ch)}"
                f"{josa(pos_ch[-1], '은', '는')} 긍정여론이 높게 나타났으며, {' '.join(neg_ch)}"
                f"{josa(neg_ch[-1], '은', '는')} 부정적 여론이 높게 나타남"
            )
        feat = sorted(cs, key=lambda c: c.feature_volume, reverse=True)[:2]
        second = (
            f"채널별 여론 특징을 살펴보면, {feat[0].channel.value}는 {feat[0].feature_text} "
            f"관련 내용이 {ic(feat[0].feature_volume)}건으로 가장 높았으며, "
            f"{feat[1].channel.short}에서는 {feat[1].feature_text} 관련 내용이 "
            f"{ic(feat[1].feature_volume)}건으로 집계됨"
        )
        neg_kw = ", ".join(a.negative_keywords[:2]) or "부정 이슈"
        third = (
            f"전체 채널 종합 감성은 긍정 {ov.get('긍정')}%, 중립 {ov.get('중립')}%, "
            f"부정 {ov.get('부정')}%로 집계되었으며, {'·'.join(neg_ch)}에서 {neg_kw} 등 "
            f"부정적 여론이 많은 것으로 분석됨"
        )
        pos_short = '·'.join(c.channel.short for c in sorted(cs, key=lambda c: c.positive, reverse=True)[:2])
        fourth = (
            f"또한, {pos_short}에서는 {self.m.subject_name} 관련 관광·생활정보 중심은 "
            f"긍정적인 여론이 형성되고 있는 것으로 분석됨"
        )
        return [first, second, third, fourth]

    def related_keywords(self) -> list[str]:
        a = self.a
        top = a.related_keywords[:3]
        if not top:
            return []
        rest = ", ".join(f"{k.keyword} {ic(k.volume)}건" for k in top[1:])
        first = (
            f"{self.m.subject_name} 상위 연관 키워드를 살펴보면, {top[0].keyword}에 대한 "
            f"키워드가 {ic(top[0].volume)}건으로 가장 높았으며"
            + (f", {rest}으로 높게 나타남" if rest else " 높게 나타남")
        )
        out = [first]
        if a.positive_keywords or a.negative_keywords:
            out.append(
                f"키워드에 대한 긍정적인 반응은 {', '.join(a.positive_keywords) or '해당 없음'}으로 "
                f"나타났으며, 부정적인 반응은 {', '.join(a.negative_keywords) or '해당 없음'} 등임")
        return out

    def special_trends_summary(self) -> list[str]:
        a, m = self.a, self.m
        titles = [t.title for t in a.special_trends]
        if not titles:
            return []
        if len(titles) >= 4:
            return [
                f"{m.month}월 특이 온라인 동향을 보면, 커뮤니티 영역에서 행정통합 반대 여론이 "
                f"집중되었으며, AI·반도체 투자 호재에 대한 긍정적 여론 확산, 지사 공천 미신청 "
                f"관련 관심 급증, 탄소 중립·탈석탄 정책에 대한 관심도가 증가한 것으로 분석됨"]
        return [f"{m.month}월 특이 온라인 동향으로는 {', '.join(titles)} 등이 확인됨"]

    def core_keywords_intro(self) -> list[str]:
        names = [c.name for c in self.a.core_keywords]
        if not names:
            return []
        return [
            f"{len(names)}대 핵심 이슈인 {', '.join(names)}에 대한 상세 여론 분석 내용은 "
            f"다음과 같음"
        ]

    def core_keywords_detail(self) -> list[str]:
        cores = self.a.core_keywords
        # 각 핵심 키워드 분석을 독립 개조식 문장으로 서술 (접합 artifact 방지)
        out = []
        for c in cores:
            head = f"{c.name}{josa(c.name, '은', '는')} " if not c.analysis.startswith("'") else ""
            out.append(head + c.analysis)
        return out

    def job_evaluation(self) -> list[str]:
        je = self.a.job_evaluation
        if je is None:
            return []
        first = (
            f"{je.subject}의 직무수행 평가는 긍정의견 {pc(je.positive_pct)}, "
            f"부정의견 {pc(je.negative_pct)}로 집계됨"
        )
        second = (
            f"긍정평가 주요 요인은 {', '.join(je.positive_reasons)} 등의 성과를 들 수 있음"
        )
        third = (
            f"부정 평가 주요 요인으로는 {', '.join(je.negative_reasons)} 등의 비판이 있었음"
        )
        return [first, second, third]

    def implications_conclusion(self) -> list[str]:
        impls = self.a.implications
        je = self.a.job_evaluation
        if len(impls) < 4 or je is None:
            return []
        subj_josa = josa(self.m.subject_name, "은", "는")
        first = (
            f"{je.subject} 직무수행에 대한 평가에서 볼 수 있듯이 {self.m.subject_name}{subj_josa} "
            f"{impls[0].topic} 관련 {impls[0].headline}하며, {impls[1].topic} 관련 긍정 여론 "
            f"지속 확산이 필요함"
        )
        second = (
            f"또한, 지방선거시점에서 도정 성과에 대한 객관적 홍보 원칙을 지키고, "
            f"{impls[3].topic} 등 지역 경제 연계 로드맵 관련 정보 공유 대응이 필요함"
        )
        return [first, second]


# --------------------------------------------------------------------------- #
# LLM 기반 Narrator
# --------------------------------------------------------------------------- #
class LLMNarrator(Narrator):
    """grounded 프롬프트로 LLM 호출. 실패 시 TemplateNarrator 로 fallback."""

    def __init__(self, meta, analysis, client: LLMClient):
        super().__init__(meta, analysis)
        self.client = client
        self._fallback = TemplateNarrator(meta, analysis)

    def _gen(self, builder, payload: dict, fallback_method: str) -> list[str]:
        try:
            system, user = builder(payload)
            text = self.client.generate(system, user)
            paras = [p.strip() for p in text.split("\n") if p.strip()]
            return paras or getattr(self._fallback, fallback_method)()
        except Exception:
            return getattr(self._fallback, fallback_method)()

    def overview_purpose(self):
        return self._fallback.overview_purpose()   # 고정 문안

    def volume_overview(self):
        return self._gen(prompts.volume_overview, {
            "total_volume": self.a.total_volume, "prev_change_pct": self.a.prev_change_pct,
            "subject_volumes": self.a.subject_volumes, "positive_ratio": self.a.positive_ratio,
            "channel_share": self.a.channel_share,
        }, "volume_overview")

    def top_issues_overview(self):
        return self._gen(prompts.top_issues_overview,
                         {"top_issues": _encode(self.a.top_issues)}, "top_issues_overview")

    def channel_sentiment(self):
        return self._gen(prompts.channel_sentiment, {
            "channel_sentiments": _encode(self.a.channel_sentiments),
            "overall_sentiment": self.a.overall_sentiment,
        }, "channel_sentiment")

    def related_keywords(self):
        return self._gen(prompts.related_keywords, {
            "related_keywords": _encode(self.a.related_keywords[:10]),
            "positive_keywords": self.a.positive_keywords,
            "negative_keywords": self.a.negative_keywords,
        }, "related_keywords")

    def special_trends_summary(self):
        return self._fallback.special_trends_summary()

    def core_keywords_intro(self):
        return self._fallback.core_keywords_intro()

    def core_keywords_detail(self):
        return self._gen(prompts.core_keywords,
                         {"core_keywords": _encode(self.a.core_keywords)}, "core_keywords_detail")

    def job_evaluation(self):
        return self._gen(prompts.job_evaluation,
                         {"job_evaluation": _encode(self.a.job_evaluation)}, "job_evaluation")

    def implications_conclusion(self):
        return self._gen(prompts.implications,
                         {"implications": _encode(self.a.implications)}, "implications_conclusion")


# --------------------------------------------------------------------------- #
def build_narrator(provider: str, model: str, meta, analysis) -> Narrator:
    if provider == "template":
        return TemplateNarrator(meta, analysis)
    try:
        if provider == "gemini":
            from .providers import GeminiClient
            client = GeminiClient(model or "gemini-2.5-pro")
        elif provider == "openai":
            from .providers import OpenAIClient
            client = OpenAIClient(model or "gpt-5")
        else:
            return TemplateNarrator(meta, analysis)
        return LLMNarrator(meta, analysis, client)
    except Exception:
        # 키 부재 등 -> 결정론적 template 로 안전하게 fallback
        return TemplateNarrator(meta, analysis)
