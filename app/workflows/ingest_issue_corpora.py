"""Put issue corpora through the existing multi-query collection workflow (one 2.0 query per user issue)."""

import asyncio
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cleaning.service import CleaningService
from app.collectors.replay import ReplayCollector
from app.core.enums import WorkflowState
from app.dedup.service import DeduplicationService
from app.evidence.service import EvidenceService
from app.models.project import Query
from app.repositories.sqlalchemy import (
    SqlAlchemyCollectionRunRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyDuplicateClusterRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyQuerySetRepository,
)
from app.research.corpus import IssueCorpus, load_corpus
from app.schemas.common import ProjectId
from app.schemas.query import SearchQuery
from app.workflows.multi_query_collection_to_evidence import CollectionRequest, MultiQueryCollectionToEvidenceWorkflow


async def ingest_corpora(session: Session, project_id: ProjectId, corpora: list[IssueCorpus]) -> dict[str, dict[str, int]]:
    """Per issue: total = ingestible + held_undated + held_unmapped_channel. Held items are never stored."""
    names = [c.issue for c in corpora]
    duplicated = sorted({n for n in names if names.count(n) > 1})
    if duplicated:  # the issue name is the 2.0 query: two corpora under one name would overwrite each other
        raise ValueError(f"duplicate issue names: {duplicated}")
    collectors = {c.issue: ReplayCollector(c) for c in corpora}
    summary: dict[str, dict[str, int]] = {}
    channels_by_issue = {}
    for issue, collector in collectors.items():
        reasons = list(collector.held.values())
        usable = [channel for _, channel in collector.usable]
        summary[issue] = {"total": len(collector.corpus.items), "ingestible": len(usable),
                          "held_undated": reasons.count("undated"), "held_unmapped_channel": reasons.count("unmapped_channel")}
        channels_by_issue[issue] = list(dict.fromkeys(usable))

    queries = [SearchQuery(query=issue, channels=chs) for issue, chs in channels_by_issue.items() if chs]
    if queries:
        SqlAlchemyQuerySetRepository(session).create(project_id, queries)
        projects = SqlAlchemyProjectRepository(session)
        snapshot = projects.get_workflow(project_id)
        if snapshot is not None and snapshot.workflow_state is WorkflowState.CREATED:
            projects.advance_workflow(project_id, WorkflowState.QUERIES_READY)
        query_id = {text: qid for qid, text in session.execute(select(Query.id, Query.query).where(Query.project_id == project_id)).all()}
        requests = [
            CollectionRequest(collector=collectors[q.query], query_id=query_id[q.query], run_id=uuid4(),
                              query=SearchQuery(query=q.query, channels=[channel]))
            for q in queries for channel in q.channels
        ]
        await MultiQueryCollectionToEvidenceWorkflow(
            collection_run_repository=SqlAlchemyCollectionRunRepository(session), cleaning_service=CleaningService(),
            deduplication_service=DeduplicationService(), evidence_service=EvidenceService(),
            project_repository=SqlAlchemyProjectRepository(session), document_repository=SqlAlchemyDocumentRepository(session),
            duplicate_cluster_repository=SqlAlchemyDuplicateClusterRepository(session),
            evidence_repository=SqlAlchemyEvidenceRepository(session),
        ).run(project_id=project_id, requests=requests)
    summary["__canonical_documents__"] = {"count": SqlAlchemyDocumentRepository(session).count_canonical(project_id)}
    return summary


def ingest_corpus_files(factory, project_id: ProjectId, paths: list[Path]) -> dict[str, dict[str, int]]:
    """Load saved corpus files and ingest them in one transaction (rolled back if anything fails)."""
    from app.db.session import session_scope

    corpora = [load_corpus(p) for p in paths]
    with session_scope(factory) as session:
        return asyncio.run(ingest_corpora(session, project_id, corpora))


def main() -> None:
    import argparse
    from uuid import UUID

    from app.core.config import get_settings
    from app.db.session import create_session_factory

    p = argparse.ArgumentParser(description="Ingest saved issue corpora (corpus_*.json) into an existing project (state CREATED).")
    p.add_argument("--project-id", type=UUID, required=True)
    p.add_argument("corpus", type=Path, nargs="+")
    a = p.parse_args()
    for issue, counts in ingest_corpus_files(create_session_factory(get_settings().database_url), a.project_id, a.corpus).items():
        print(issue, counts)


if __name__ == "__main__":
    main()
