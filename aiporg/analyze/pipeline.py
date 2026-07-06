"""분석 파이프라인 오케스트레이터.

두 가지 모드:
  1) fixture 모드: 사전 산출된 AnalysisResult(json) 로드 -> 재현성 보장.
  2) live 모드: Document 리스트를 받아 전체 분석 단계 수행.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import date

from ..models import (
    AnalysisResult, ChannelSentiment, Channel, Document, Issue, Sentiment,
)
from . import cluster, keywords, ner, sentiment, volume
from .dedup import dedup

log = logging.getLogger(__name__)


class AnalysisPipeline:
    def __init__(self, seed: int = 42):
        self.seed = seed

    # ------------------------------------------------------------------ #
    @staticmethod
    def load_fixture(path: str) -> AnalysisResult:
        """사전 산출된 분석결과 json 을 AnalysisResult 로 복원."""
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return _decode_result(raw)

    # ------------------------------------------------------------------ #
    def run(self, docs: list[Document], meta, subjects: dict[str, list[str]],
            sentiment_classifier=None) -> AnalysisResult:
        """live 모드: 수집 문서 -> AnalysisResult.

        sentiment_classifier: 선택. list[str] -> list[Sentiment] 콜러블.
        지정 시 감성 라벨링에 사용(예: LLM 배치 분류), 미지정 시 사전 기반.
        """
        log.info("분석 시작: 원본 %d건", len(docs))
        docs = dedup(docs)
        log.info("중복제거 후 %d건", len(docs))

        # 감성 라벨링
        if sentiment_classifier is not None:
            texts = [d.title + " " + d.body for d in docs]
            labels = sentiment_classifier(texts)
            for d, lb in zip(docs, labels):
                d.sentiment = lb
            log.info("감성 라벨링: LLM 배치 분류 %d건", len(docs))
        else:
            for d in docs:
                d.sentiment = sentiment.classify(d.title + " " + d.body)

        # 토픽 군집화
        groups = cluster.cluster(docs)

        # 언급량/채널
        share = volume.channel_share(docs)
        daily = volume.daily_volume(docs, meta.period_start, meta.period_end)
        subj_vol = volume.subject_volumes(docs, subjects)

        # 연관 키워드
        rel = keywords.related_keywords(docs, top_k=20)

        # 채널별 감성
        ch_sents = self._channel_sentiments(docs)

        # 전체 감성
        overall = sentiment.aggregate([d.sentiment for d in docs if d.sentiment])

        # TOP 이슈 (군집 규모순)
        top_issues = self._top_issues(groups)

        # NER
        persons = [meta.leader_name]
        entities = ner.extract(docs, person_lexicon=persons)

        pos_ratio = overall.get("긍정", 0.0)

        # 실데이터에서 직접 산출 가능한 파생 지표
        core = self._core_keywords(docs, rel)
        job = self._job_evaluation(docs, meta.leader_name, meta.leader_title)
        trends = self._special_trends(top_issues)

        return AnalysisResult(
            total_volume=len(docs),
            prev_change_pct=0.0,   # 전월 데이터 연동 시 계산
            subject_volumes=subj_vol,
            positive_ratio=pos_ratio,
            channel_share=share,
            daily_volume=daily,
            top_issues=top_issues,
            channel_sentiments=ch_sents,
            overall_sentiment=overall,
            related_keywords=rel,
            positive_keywords=[k.keyword for k in rel if k.sentiment == Sentiment.POSITIVE][:5],
            negative_keywords=[k.keyword for k in rel if k.sentiment == Sentiment.NEGATIVE][:5],
            special_trends=trends,
            core_keywords=core,
            job_evaluation=job,
            implications=[],       # 시사점·대응제언은 전문 분석/LLM 서술 단계 산출물
            entities=entities,
        )

    # ------------------------------------------------------------------ #
    def _core_keywords(self, docs, rel):
        """상위 연관 키워드 4개를 실측 언급량·감성으로 핵심 키워드화."""
        from ..models import CoreKeyword
        out = []
        for k in rel[:4]:
            reps = [d for d in docs if k.keyword in (d.title + d.body)]
            rep = reps[0].title if reps else ""
            out.append(CoreKeyword(
                name=k.keyword, volume=k.volume, sentiment=k.sentiment, change_pct=0.0,
                analysis=f"'{k.keyword}' 관련 언급이 {k.volume}건으로 집계되었으며, "
                         f"대표 기사로 「{rep[:40]}」 등이 확인됨",
                evidence=[reps[0].url] if reps else [],
            ))
        return out

    def _job_evaluation(self, docs, leader_name, leader_title):
        """도지사(인물) 언급 문서의 실측 감성으로 직무평가 산출."""
        from ..models import JobEvaluation
        ldocs = [d for d in docs if leader_name in (d.title + d.body)]
        if len(ldocs) < 3:
            return None   # 표본 부족 시 생략
        agg = sentiment.aggregate([d.sentiment for d in ldocs if d.sentiment])
        from .keywords import tfidf_keywords
        pos_docs = [d for d in ldocs if d.sentiment == Sentiment.POSITIVE]
        neg_docs = [d for d in ldocs if d.sentiment == Sentiment.NEGATIVE]
        pos_kw = [w for w, _ in tfidf_keywords(pos_docs, 3)] if pos_docs else []
        neg_kw = [w for w, _ in tfidf_keywords(neg_docs, 3)] if neg_docs else []
        return JobEvaluation(
            subject=f"{leader_name} {leader_title}",
            positive_pct=agg["긍정"], negative_pct=agg["부정"],
            positive_reasons=[f"{k} 관련 긍정 언급" for k in pos_kw] or ["긍정 언급 다수"],
            negative_reasons=[f"{k} 관련 부정 언급" for k in neg_kw] or ["부정 언급 존재"],
        )

    def _special_trends(self, top_issues):
        """상위 이슈 3건을 특이 동향으로 요약 (실측 대표 기사 기반)."""
        from ..models import SpecialTrend
        trends = []
        for i in top_issues[:3]:
            trends.append(SpecialTrend(
                f"{i.category} 이슈 부각 ({i.sentiment.value})",
                f"「{i.title[:50]}」 관련 {i.volume}건 언급"))
        return trends

    # ------------------------------------------------------------------ #
    def _channel_sentiments(self, docs: list[Document]) -> list[ChannelSentiment]:
        out = []
        by_channel: dict[Channel, list[Document]] = {}
        for d in docs:
            by_channel.setdefault(d.channel, []).append(d)
        from .keywords import tfidf_keywords
        for ch, ds in by_channel.items():
            agg = sentiment.aggregate([d.sentiment for d in ds if d.sentiment])
            top_kw = [w for w, _ in tfidf_keywords(ds, 3)]
            feature = "·".join(top_kw) + " 등" if top_kw else "도정·현안"
            out.append(ChannelSentiment(
                channel=ch, positive=agg["긍정"], neutral=agg["중립"],
                negative=agg["부정"], feature_text=feature, feature_volume=len(ds),
            ))
        out.sort(key=lambda c: c.feature_volume, reverse=True)
        return out

    def _top_issues(self, groups: dict[str, list[Document]], k: int = 10) -> list[Issue]:
        ranked = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)[:k]
        issues = []
        for rank, (cat, ds) in enumerate(ranked, 1):
            rep = max(ds, key=lambda d: d.views + d.comments + d.likes)
            sents = [d.sentiment for d in ds if d.sentiment]
            dominant = Counter(s.value for s in sents).most_common(1)
            issues.append(Issue(
                rank=rank, category=cat, title=rep.title, volume=len(ds),
                change_pct=0.0,
                sentiment=Sentiment(dominant[0][0]) if dominant else Sentiment.NEUTRAL,
                evidence=[rep.url],
            ))
        return issues


# ---------------------------------------------------------------------- #
# fixture 역직렬화
# ---------------------------------------------------------------------- #
def _decode_result(raw: dict) -> AnalysisResult:
    from ..models import (
        CoreKeyword, Implication, JobEvaluation, KeywordStat, SpecialTrend,
    )

    def S(v):
        return Sentiment(v) if v else Sentiment.NEUTRAL

    issues = [Issue(
        rank=i["rank"], category=i["category"], title=i["title"], volume=i["volume"],
        change_pct=i["change_pct"], sentiment=S(i["sentiment"]),
        evidence=i.get("evidence", []), ai_comment=i.get("ai_comment", ""),
    ) for i in raw.get("top_issues", [])]

    ch_sents = [ChannelSentiment(
        channel=Channel(c["channel"]), positive=c["positive"], neutral=c["neutral"],
        negative=c["negative"], feature_text=c.get("feature_text", ""),
        feature_volume=c.get("feature_volume", 0),
    ) for c in raw.get("channel_sentiments", [])]

    rel = [KeywordStat(k["keyword"], k["weight"], k["volume"], S(k.get("sentiment")))
           for k in raw.get("related_keywords", [])]

    trends = [SpecialTrend(t["title"], t["detail"]) for t in raw.get("special_trends", [])]

    cores = [CoreKeyword(
        name=c["name"], volume=c["volume"], sentiment=S(c["sentiment"]),
        change_pct=c["change_pct"], analysis=c["analysis"], evidence=c.get("evidence", []),
        summary=c.get("summary", ""), positive_point=c.get("positive_point", ""),
        negative_point=c.get("negative_point", ""), keywords=c.get("keywords", []),
    ) for c in raw.get("core_keywords", [])]

    je = raw.get("job_evaluation")
    job = JobEvaluation(
        subject=je["subject"], positive_pct=je["positive_pct"],
        negative_pct=je["negative_pct"], positive_reasons=je["positive_reasons"],
        negative_reasons=je["negative_reasons"],
        neutral_pct=je.get("neutral_pct", 0.0), comparison=je.get("comparison", {}),
        highlight_region=je.get("highlight_region", ""),
    ) if je else None

    impls = [Implication(m["topic"], m["headline"], m["body"], m["response"])
             for m in raw.get("implications", [])]

    return AnalysisResult(
        total_volume=raw["total_volume"], prev_change_pct=raw["prev_change_pct"],
        subject_volumes=raw.get("subject_volumes", {}),
        subject_changes=raw.get("subject_changes", {}),
        positive_ratio=raw.get("positive_ratio", 0.0),
        channel_share=raw.get("channel_share", {}),
        daily_volume=raw.get("daily_volume", {}),
        top_issues=issues, channel_sentiments=ch_sents,
        overall_sentiment=raw.get("overall_sentiment", {}),
        related_keywords=rel,
        positive_keywords=raw.get("positive_keywords", []),
        negative_keywords=raw.get("negative_keywords", []),
        special_trends=trends, core_keywords=cores, job_evaluation=job,
        implications=impls, entities=raw.get("entities", {}),
    )
