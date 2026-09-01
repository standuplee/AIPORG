"""Evidence-backed issue candidate discovery."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from uuid import UUID, uuid4

from app.core.enums import ChannelType
from app.schemas.fact import FactSchema
from app.schemas.issue import IssueCandidateSchema


class IssueDiscoveryService:
    """Group facts by normalized entity signatures without inventing labels."""

    def discover(
        self,
        facts: Sequence[FactSchema],
        *,
        source_by_document: Mapping[UUID, str],
        channel_by_document: Mapping[UUID, ChannelType],
    ) -> list[IssueCandidateSchema]:
        groups: dict[tuple[str, ...], list[FactSchema]] = defaultdict(list)
        for fact in facts:
            entities = tuple(sorted({entity.strip() for entity in fact.entities if entity.strip()}, key=str.casefold))
            if entities:
                groups[entities].append(fact)

        candidates: list[IssueCandidateSchema] = []
        for entities, grouped_facts in groups.items():
            fact_ids = [fact.fact_id for fact in grouped_facts]
            document_ids = {
                document_id
                for fact in grouped_facts
                for document_id in fact.evidence_document_ids
            }
            missing_sources = document_ids - source_by_document.keys()
            missing_channels = document_ids - channel_by_document.keys()
            if missing_sources or missing_channels:
                raise ValueError("source and channel provenance are required for every issue document")
            sources = {source_by_document[document_id] for document_id in document_ids}
            channels = {channel_by_document[document_id] for document_id in document_ids}
            candidates.append(
                IssueCandidateSchema(
                    issue_id=uuid4(),
                    label="·".join(entities),
                    fact_ids=fact_ids,
                    document_count=len(document_ids),
                    source_count=len(sources),
                    channel_count=len(channels),
                )
            )
        return sorted(
            candidates,
            key=lambda candidate: (-candidate.document_count, -candidate.source_count, candidate.label),
        )
