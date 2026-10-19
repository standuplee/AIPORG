"""Evidence-backed issue candidate discovery."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from uuid import UUID, uuid4

from app.core.enums import ChannelType
from app.schemas.fact import FactSchema
from app.schemas.issue import IssueCandidateSchema


class IssueDiscoveryService:
    """Group facts by the keyword (query) that found their evidence.

    2026-10-19 decision (HANDOFF.md 20차): grouping used to key on
    ``fact.entities`` (which of a fixed org/person/region term list appears
    in the claim text) -- a signal unrelated to what the user actually
    searched for. A real monthly run confirmed the problem concretely: 4
    keywords produced 6 oddly-shaped issues, with one label absorbing most
    of the facts because "충남" happened to appear in most claims regardless
    of topic. The query a document was found under is the one thing users
    actually typed, and gives the "one issue per monthly keyword" shape the
    report needs -- so it replaces entities as the grouping key. A fact
    whose evidence spans more than one query (rare -- the same article found
    under two keywords) is assigned to whichever query is most common among
    its evidence documents, tie-broken alphabetically for determinism.
    """

    def discover(
        self,
        facts: Sequence[FactSchema],
        *,
        source_by_document: Mapping[UUID, str],
        channel_by_document: Mapping[UUID, ChannelType],
        query_by_document: Mapping[UUID, str],
    ) -> list[IssueCandidateSchema]:
        groups: dict[str, list[FactSchema]] = defaultdict(list)
        for fact in facts:
            missing_queries = set(fact.evidence_document_ids) - query_by_document.keys()
            if missing_queries:
                raise ValueError("query provenance is required for every issue document")
            queries = [query_by_document[document_id] for document_id in fact.evidence_document_ids]
            counts = Counter(queries)
            top_count = max(counts.values())
            primary_query = min(query for query, count in counts.items() if count == top_count)
            groups[primary_query].append(fact)

        candidates: list[IssueCandidateSchema] = []
        for query_text, grouped_facts in groups.items():
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
                    label=query_text,
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
