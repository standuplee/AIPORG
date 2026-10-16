"""Pure narrative templates over existing contracts, with strict output checks."""

from collections.abc import Sequence
import re

from app.core.enums import FactStatus
from app.schemas.analytics import AnalyticsSnapshotSchema
from app.schemas.evidence import EvidenceSchema
from app.schemas.fact import FactSchema
from app.schemas.narrative import NarrativeContext


class TemplateNarrativeService:
    """Quote supported claims and render stored counts without interpreting them."""

    def render(
        self,
        contexts: Sequence[NarrativeContext],
        analytics: AnalyticsSnapshotSchema,
        evidence: Sequence[EvidenceSchema],
    ) -> str:
        sentences = []
        metrics = analytics.metrics
        if "unique_documents" in metrics:
            count = metrics["unique_documents"]
            self._validate_count(count)
            document_ids = metrics.get("document_ids")
            if (
                not isinstance(document_ids, list)
                or not all(isinstance(item, str) for item in document_ids)
                or len(set(document_ids)) != count
                or len(document_ids) != count
            ):
                raise ValueError("document count requires matching analytics provenance")
            sentences.append(f"저장된 문서 기준 분석기간 언급량은 {count}건으로 집계됨.")

        facts = {}
        for context in contexts:
            for fact in context.facts:
                if fact.fact_id not in context.issue.fact_ids:
                    raise ValueError("narrative fact is not linked to its issue")
                if fact.status not in {FactStatus.VERIFIED, FactStatus.SUPPORTED}:
                    continue
                previous = facts.get(fact.fact_id)
                if previous is not None and previous != fact:
                    raise ValueError("conflicting narrative fact inputs")
                facts[fact.fact_id] = fact
        for fact_id in sorted(facts, key=str):
            sentences.append(self.render_fact(facts[fact_id], analytics, evidence))
        return "\n".join(sentences)

    def render_fact(
        self,
        fact: FactSchema,
        analytics: AnalyticsSnapshotSchema,
        evidence: Sequence[EvidenceSchema],
    ) -> str:
        if fact.status not in {FactStatus.VERIFIED, FactStatus.SUPPORTED}:
            raise ValueError("narrative requires a verified or supported fact")
        claim = " ".join(fact.claim.split())
        if not claim:
            raise ValueError("narrative fact claim cannot be empty")
        if not fact.evidence_document_ids:
            raise ValueError("fact requires linked project evidence")
        supported_documents = {
            item.document_id
            for item in evidence
            if item.project_id == analytics.project_id
            and claim in re.split(r"(?<=[.!?])\s+", " ".join(item.excerpt.split()))
        }
        if not set(fact.evidence_document_ids) <= supported_documents:
            raise ValueError("fact claim is absent from linked project evidence")
        return f"근거 문서에서 다음 내용이 확인됨: 「{claim}」"

    def validate(
        self,
        text: str,
        contexts: Sequence[NarrativeContext],
        analytics: AnalyticsSnapshotSchema,
        evidence: Sequence[EvidenceSchema],
    ) -> None:
        """Reject any wording not produced by the grounded deterministic template.

        Exact template equivalence is stronger than a token whitelist: it also
        rejects changed negation or relationships between allowed names/numbers.
        """
        if text != self.render(contexts, analytics, evidence):
            raise ValueError("narrative differs from the supported template output")

    @staticmethod
    def _validate_count(value: object) -> None:
        if type(value) is not int or value < 0:
            raise ValueError("analytics document count must be a nonnegative integer")
