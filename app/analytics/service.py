"""Deterministic analytics over persisted canonical documents; no network or LLM."""

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import timedelta
import hashlib
import json
import re
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.enums import FactStatus, SentimentLabel
from app.schemas.analytics import AnalyticsSnapshotSchema
from app.schemas.common import (
    AnalysisPeriodSchema,
    ComparisonPeriodSchema,
    PeriodSchema,
    ProjectId,
    VersionedRunSchema,
)
from app.schemas.document import CleanDocument
from app.schemas.fact import FactSchema
from app.schemas.issue import IssueSchema


# General/proper nouns (NNG/NNP) anchor a keyword phrase. Real-data testing
# (2026-10-19) found that counting single noun morphemes split real compound
# words apart ("집중호우" as "집중"/"호우", "재난대응" as "재난"/"대응") --
# unlike a reference monthly report's keyword cards, which show compound
# phrases ("집중호우", "AI반도체", "행정통합공론화"), never isolated single
# nouns. A maximal run of directly-adjacent tokens (no whitespace/particle
# between them) is merged into one phrase as long as the run contains at
# least one real noun -- so a bound noun or number never surfaces alone
# (NNB/SN carry no content by themselves, e.g. "것"/"수"/"때문", bare "123"),
# but can be part of a longer phrase ("취임1개월평가" if written with no
# spaces), and a lone foreign-script token ("AI", a leaked "var") is dropped
# unless it's directly touching a real noun ("AI"+"반도체" -> "AI반도체").
_KEYWORD_CORE_TAGS = frozenset({"NNG", "NNP"})
_KEYWORD_MERGEABLE_TAGS = _KEYWORD_CORE_TAGS | frozenset({"SL", "SN", "NNB", "XSN"})
_kiwi_instance = None
_kiwi_unavailable = False


def _get_kiwi():
    global _kiwi_instance, _kiwi_unavailable
    if _kiwi_unavailable:
        return None
    if _kiwi_instance is None:
        try:
            from kiwipiepy import Kiwi
            _kiwi_instance = Kiwi()
        except Exception:
            _kiwi_unavailable = True
            return None
    return _kiwi_instance


def _merge_adjacent_noun_phrases(text: str, kiwi) -> list[str]:
    phrases: list[str] = []
    current_forms: list[str] = []
    current_tags: list[str] = []
    previous_end: int | None = None

    def flush() -> None:
        if current_forms and any(tag in _KEYWORD_CORE_TAGS for tag in current_tags):
            phrases.append("".join(current_forms))
        current_forms.clear()
        current_tags.clear()

    for token in kiwi.tokenize(text):
        adjacent = previous_end is not None and token.start == previous_end
        if token.tag in _KEYWORD_MERGEABLE_TAGS:
            if not adjacent and current_forms:
                flush()
            current_forms.append(token.form)
            current_tags.append(token.tag)
        else:
            flush()
        previous_end = token.start + token.len
    flush()
    return [phrase.casefold() for phrase in phrases if len(phrase) >= 2]


def _extract_keyword_tokens(text: str) -> list[str]:
    """Tokenize to keyword-phrase candidates: adjacent-noun compounds via
    kiwipiepy, with a plain-regex fallback (numbers excluded, no merging)
    if kiwipiepy is unavailable."""

    kiwi = _get_kiwi()
    if kiwi is not None:
        return _merge_adjacent_noun_phrases(text, kiwi)
    return re.findall(r"[^\W\d_]{2,}", text.casefold())


class AnalyticsService:
    """Compute observed-document statistics with per-bucket document provenance.

    Input must be the repository's canonical selection. Sentiment is aggregated
    only from existing metadata labels, never inferred from issue defaults.
    Keywords are literal case-folded letter tokens (length >= 2), not linguistic
    entities. Absent comparison observations do not establish a zero baseline.
    """

    def build(
        self,
        project_id: ProjectId,
        run: VersionedRunSchema,
        documents: Sequence[CleanDocument],
        *,
        analysis_period: AnalysisPeriodSchema,
        comparison_period: ComparisonPeriodSchema | None,
        issues: Sequence[IssueSchema] = (),
        facts_by_id: Mapping[UUID, FactSchema] | None = None,
        timezone_name: str = "Asia/Seoul",
    ) -> AnalyticsSnapshotSchema:
        zone = ZoneInfo(timezone_name)
        unique: dict[UUID, CleanDocument] = {}
        for document in documents:
            existing = unique.get(document.document_id)
            if existing is not None and existing != document:
                raise ValueError("conflicting records for one document ID")
            unique[document.document_id] = document
        ordered = sorted(unique.values(), key=lambda item: str(item.document_id))
        urls = [document.canonical_url for document in ordered]
        if len(urls) != len(set(urls)):
            raise ValueError("analytics requires unique canonical URLs")

        def in_period(document: CleanDocument, period: PeriodSchema) -> bool:
            return (
                document.published_at is not None
                and period.start <= document.published_at.astimezone(zone).date() <= period.end
            )

        current = [document for document in ordered if in_period(document, analysis_period)]
        previous = (
            [document for document in ordered if in_period(document, comparison_period)]
            if comparison_period is not None else []
        )
        channels = self._groups(current, lambda item: item.channel.value if item.channel else "unclassified")
        sources = self._groups(current, lambda item: item.source.strip() if item.source and item.source.strip() else "unclassified")
        sentiment_values = {label.value for label in SentimentLabel}

        def sentiment(document: CleanDocument) -> str:
            label = document.metadata.get("sentiment")
            return label if isinstance(label, str) and label in sentiment_values else "unclassified"

        sentiments = self._groups(current, sentiment)
        daily = self._groups(current, lambda item: item.published_at.astimezone(zone).date().isoformat())
        day = analysis_period.start
        while day <= analysis_period.end:
            daily.setdefault(day.isoformat(), [])
            day += timedelta(days=1)

        keyword_counts: Counter[str] = Counter()
        keyword_documents: dict[str, list[str]] = defaultdict(list)
        for document in current:
            counts = Counter(_extract_keyword_tokens(f"{document.title}\n{document.body}"))
            keyword_counts.update(counts)
            for token in sorted(counts):
                keyword_documents[token].append(str(document.document_id))

        comparison = {
            "status": "period_not_configured" if comparison_period is None else "no_comparison_documents",
            "period": comparison_period.model_dump(mode="json") if comparison_period else None,
            "document_ids": self._ids(previous),
            "unique_documents": None,
            "change": None,
            "change_percent": None,
        }
        if previous:
            comparison.update(
                status="available",
                unique_documents=len(previous),
                change=len(current) - len(previous),
                change_percent=(len(current) - len(previous)) / len(previous) * 100,
            )

        facts_by_id = facts_by_id or {}
        issue_metrics = []
        current_by_id = {document.document_id: document for document in current}
        for issue in sorted(issues, key=lambda item: str(item.issue_id)):
            accepted = []
            excluded = []
            linked_ids = set()
            for fact_id in sorted(set(issue.fact_ids), key=str):
                fact = facts_by_id.get(fact_id)
                if fact is None or fact.fact_id != fact_id:
                    raise ValueError("issue references an unknown or mismatched fact")
                if fact.status not in {FactStatus.VERIFIED, FactStatus.SUPPORTED}:
                    excluded.append(str(fact_id))
                    continue
                accepted.append(str(fact_id))
                linked_ids.update(fact.evidence_document_ids)
            linked = [current_by_id[key] for key in sorted(linked_ids & current_by_id.keys(), key=str)]
            issue_sources = self._groups(linked, lambda item: item.source.strip() if item.source and item.source.strip() else "unclassified")
            issue_channels = self._groups(linked, lambda item: item.channel.value if item.channel else "unclassified")
            issue_metrics.append({
                "issue_id": str(issue.issue_id),
                "label": issue.label,
                "fact_ids": accepted,
                "excluded_fact_ids": excluded,
                "document_ids": self._ids(linked),
                "document_count": len(linked),
                "source_count": len({item.source.strip() for item in linked if item.source and item.source.strip()}),
                "channel_count": len({item.channel for item in linked if item.channel is not None}),
                "source_mentions": self._counts(issue_sources),
                "channel_mentions": self._counts(issue_channels),
                "source_document_ids": issue_sources,
                "channel_document_ids": issue_channels,
            })

        basis = {
            "method": "canonical_document_analytics_v1",
            "selection": "cleaned_project_documents_excluding_duplicate_members",
            "timezone": timezone_name,
            "analysis_period": analysis_period.model_dump(mode="json"),
            "comparison_period": comparison_period.model_dump(mode="json") if comparison_period else None,
            "sentiment": "existing_metadata_sentiment_only",
            "keywords": "kiwipiepy_adjacent_noun_phrase_merge_min_length_2_casefold"
            if _get_kiwi() is not None
            else "title_and_body_casefold_letter_tokens_min_length_2",
            "comparison": "observed_document_totals_without_period_length_normalization",
            "coverage": "stored_documents_only_not_verified_collection_completeness",
        }
        fingerprint = {
            "basis": basis,
            "documents": [item.model_dump(mode="json") for item in ordered],
            "issues": [item.model_dump(mode="json") for item in sorted(issues, key=lambda item: str(item.issue_id))],
            "facts": [facts_by_id[key].model_dump(mode="json") for key in sorted(facts_by_id, key=str)],
        }
        basis["input_sha256"] = hashlib.sha256(
            json.dumps(fingerprint, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        return AnalyticsSnapshotSchema(
            project_id=project_id,
            run=run,
            metrics={
                "basis": basis,
                "unique_documents": len(current),
                "document_ids": self._ids(current),
                "input_document_ids": self._ids(ordered),
                "undated_document_ids": self._ids([item for item in ordered if item.published_at is None]),
                "channel_mentions": self._counts(channels),
                "channel_document_ids": channels,
                "source_mentions": self._counts(sources),
                "source_document_ids": sources,
                "unclassified_documents": len(channels.get("unclassified", [])),
                "sentiment_distribution": {label: len(sentiments.get(label, [])) for label in sorted(sentiment_values | {"unclassified"})},
                "sentiment_document_ids": sentiments,
                "daily_mentions": self._counts(daily),
                "daily_document_ids": dict(sorted(daily.items())),
                "keyword_frequencies": dict(sorted(keyword_counts.items())),
                "keyword_document_ids": dict(sorted(keyword_documents.items())),
                "comparison": comparison,
                "issues": issue_metrics,
            },
        )

    @staticmethod
    def _ids(documents: Sequence[CleanDocument]) -> list[str]:
        return sorted(str(document.document_id) for document in documents)

    @staticmethod
    def _groups(
        documents: Sequence[CleanDocument], key: Callable[[CleanDocument], str],
    ) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = defaultdict(list)
        for document in documents:
            groups[key(document)].append(str(document.document_id))
        return {label: sorted(ids) for label, ids in sorted(groups.items())}

    @staticmethod
    def _counts(groups: Mapping[str, Sequence[str]]) -> dict[str, int]:
        return {label: len(ids) for label, ids in sorted(groups.items())}
