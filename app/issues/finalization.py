"""Convert evidence-backed issue candidates into persisted issue contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from app.schemas.fact import FactSchema
from app.schemas.issue import IssueCandidateSchema, IssueDetailSchema, IssueSchema
from app.sentiment.service import SentimentService


class IssueFinalizationService:
    """Build issue details only from already validated fact claims.

    Each subissue's sentiment/stance is classified from that same fact
    claim text (deterministic lexicon, see app/sentiment/service.py) --
    no new wording, no LLM call. Previously this hardcoded every subissue
    to SentimentLabel.NEUTRAL; see HANDOFF.md for why that placeholder was
    replaced with a real classification.
    """

    def __init__(self, sentiment_service: SentimentService | None = None) -> None:
        self.sentiment_service = sentiment_service or SentimentService()

    def finalize(
        self,
        candidates: Sequence[IssueCandidateSchema],
        *,
        facts_by_id: Mapping[UUID, FactSchema],
    ) -> list[IssueSchema]:
        issues = []
        for candidate in candidates:
            facts = []
            for fact_id in candidate.fact_ids:
                fact = facts_by_id.get(fact_id)
                if fact is None:
                    raise ValueError("issue candidate references an unknown fact")
                facts.append(fact)
            details = [
                IssueDetailSchema(
                    label=candidate.label,
                    policy=fact.claim,
                    summary=fact.claim,
                    sentiment=self.sentiment_service.classify_sentiment(fact.claim),
                    stance=self.sentiment_service.classify_stance(fact.claim),
                )
                for fact in facts
            ]
            issues.append(IssueSchema(
                **candidate.model_dump(),
                subissues=details,
            ))
        return issues
