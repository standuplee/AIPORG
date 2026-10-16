"""Convert evidence-backed issue candidates into persisted issue contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from app.core.enums import SentimentLabel
from app.schemas.fact import FactSchema
from app.schemas.issue import IssueCandidateSchema, IssueDetailSchema, IssueSchema


class IssueFinalizationService:
    """Build issue details only from already validated fact claims."""

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
                    sentiment=SentimentLabel.NEUTRAL,
                )
                for fact in facts
            ]
            issues.append(IssueSchema(
                **candidate.model_dump(),
                subissues=details,
            ))
        return issues
