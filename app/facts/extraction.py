"""Deterministic fact extraction from stored evidence and documents."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date
from uuid import NAMESPACE_URL, UUID, uuid5

from app.core.enums import ConfidenceGrade, FactStatus
from app.schemas.common import ProjectId
from app.schemas.document import CleanDocument
from app.schemas.evidence import EvidenceSchema
from app.schemas.fact import FactSchema


class FactExtractionService:
    """Promote evidence sentences to facts without generating new wording."""

    def extract(
        self,
        project_id: ProjectId,
        evidence: Sequence[EvidenceSchema],
        *,
        documents: Mapping[UUID, CleanDocument],
        entity_terms: Sequence[str],
    ) -> list[FactSchema]:
        grouped: dict[tuple[str, date, tuple[str, ...]], list[CleanDocument]] = defaultdict(list)
        for item in evidence:
            if item.project_id != project_id:
                raise ValueError("evidence project_id does not match")
            document = documents.get(item.document_id)
            if document is None:
                raise ValueError("every evidence record requires its source document")
            if document.published_at is None:
                raise ValueError("fact source document requires published_at")
            claim = self._first_sentence(item.excerpt)
            if not claim:
                raise ValueError("fact claim cannot be empty")
            entities = tuple(dict.fromkeys(
                term.strip()
                for term in entity_terms
                if term.strip() and term.casefold() in claim.casefold()
            ))
            grouped[(claim, document.published_at.date(), entities)].append(document)

        facts = []
        for (claim, event_date, entities), grouped_documents in grouped.items():
            document_ids = sorted(
                {document.document_id for document in grouped_documents},
                key=lambda value: value.hex,
            )
            sources = {
                document.source.strip()
                for document in grouped_documents
                if document.source and document.source.strip()
            }
            identity = uuid5(
                NAMESPACE_URL,
                f"{project_id}:{event_date}:{claim}:{'|'.join(entities)}",
            )
            facts.append(FactSchema(
                fact_id=identity,
                claim=claim,
                event_date=event_date,
                entities=list(entities),
                evidence_document_ids=document_ids,
                source_count=len(sources),
                confidence=ConfidenceGrade.D,
                status=FactStatus.UNCERTAIN,
            ))
        return sorted(facts, key=lambda fact: (fact.event_date, fact.claim, fact.fact_id.hex))

    @staticmethod
    def _first_sentence(excerpt: str) -> str:
        normalized = " ".join(excerpt.split())
        if not normalized:
            return ""
        return re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)[0]
