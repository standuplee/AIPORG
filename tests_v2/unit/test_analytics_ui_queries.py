from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import event

from app.repositories.sqlalchemy import (
    SqlAlchemyAnalyticsRepository, SqlAlchemyDocumentRepository,
    SqlAlchemyDuplicateClusterRepository, SqlAlchemyEvidenceRepository,
    SqlAlchemyProjectRepository,
)
from app.schemas.analytics import AnalyticsSnapshotSchema
from app.schemas.common import VersionedRunSchema
from app.schemas.document import RawDocument, CleanDocument, DuplicateClusterSchema
from app.schemas.evidence import EvidenceSchema
from app.core.enums import ChannelType
from tests_v2.unit.test_sqlalchemy_repositories import _factory, _project


NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def test_summary_empty_scoped_and_bounded_latest_projection():
    with _factory()() as session:
        pid = SqlAlchemyProjectRepository(session).create(_project()).project_id
        repo = SqlAlchemyAnalyticsRepository(session)
        assert repo.get_latest_summary(pid) is None
        for count in (1, 2):
            repo.create(AnalyticsSnapshotSchema(project_id=pid, run=VersionedRunSchema(
                run_id=uuid4(), input_version='v1', output_version='v1',
                created_at=NOW.replace(day=count)), metrics={
                    'unique_documents': count,
                    'channel_mentions': {'news': count, 'invalid': '9'},
                    'sentiment_distribution': {'neutral': count},
                    'keyword_frequencies': {f'k{i:03}': 10 for i in range(100)},
                    'keyword_document_ids': {'big': ['provenance' * 1000] * 100},
                    'comparison': {'status': 'available', 'unique_documents': 1,
                                   'change': 1, 'change_percent': 100, 'document_ids': ['secret']},
                }))
        statements = []
        event.listen(session.bind, 'before_cursor_execute', lambda c, cu, s, p, co, e: statements.append(s))
        result = repo.get_latest_summary(pid)
        assert result == {
            'unique_documents': 2, 'comment_count': 0,
            'channel_mentions': {'news': 2}, 'sentiment_distribution': {'neutral': 2},
            'comparison': {'status': 'available', 'unique_documents': 1, 'change': 1, 'change_percent': 100},
            'top_keywords': [{'keyword': f'k{i:03}', 'count': 10} for i in range(30)],
        }
        assert repo.get_latest_summary(uuid4()) is None
        assert all('SELECT analytics_snapshots.metrics ' not in sql for sql in statements)
        assert any('json_each' in sql for sql in statements)


def test_summary_labels_groups_and_numeric_values_are_bounded():
    with _factory()() as session:
        pid = SqlAlchemyProjectRepository(session).create(_project()).project_id
        repo = SqlAlchemyAnalyticsRepository(session)
        repo.create(AnalyticsSnapshotSchema(project_id=pid, run=VersionedRunSchema(
            run_id=uuid4(), input_version='v1', output_version='v1', created_at=NOW), metrics={
                'channel_mentions': {str(i) + 'x' * 500: i for i in range(50)},
                'sentiment_distribution': {'bad': [], 'bool': True, 'good': 2},
                'keyword_frequencies': {'long' * 100: 100, 'bad': {}, 'lower': 1},
            }))
        result = repo.get_latest_summary(pid)
        assert len(result['channel_mentions']) == 30
        assert all(len(k) <= 300 for k in result['channel_mentions'])
        assert result['sentiment_distribution'] == {'good': 2}
        assert result['top_keywords'] == [{'keyword': ('long' * 100)[:300], 'count': 100}, {'keyword': 'lower', 'count': 1}]


def test_document_page_count_dedup_scope_clipping_and_evidence_count():
    with _factory()() as session:
        projects = SqlAlchemyProjectRepository(session)
        pid = projects.create(_project()).project_id
        other = projects.create(_project()).project_id
        repo = SqlAlchemyDocumentRepository(session)
        evidence = SqlAlchemyEvidenceRepository(session)
        assert repo.count_canonical(pid) == evidence.count_by_project(pid) == 0
        for i in range(55):
            raw = RawDocument(document_id=UUID(int=i + 1), source='s' * 400,
                channel=ChannelType.NEWS, platform='naver', title=f'{i:03}' + 't' * 400,
                url=f'https://example.com/{i}', published_at=NOW, query='q',
                body='huge body', metadata={'huge': 'data'}, collected_at=NOW)
            repo.upsert_raw(pid, raw)
            if i < 54:
                repo.upsert_clean(pid, CleanDocument(document_id=raw.document_id,
                    title=raw.title, body=raw.body, canonical_url=raw.url, cleaned_at=NOW))
        repo.upsert_raw(other, raw)
        SqlAlchemyDuplicateClusterRepository(session).create(pid, DuplicateClusterSchema(
            cluster_id=uuid4(), canonical_document=UUID(int=1), duplicates=[UUID(int=2)],
            unique_sources=['s'], distribution_count=2))
        evidence.create(EvidenceSchema(evidence_id=uuid4(), project_id=pid,
            document_id=UUID(int=1), excerpt='evidence', created_at=NOW))
        statements = []
        event.listen(session.bind, 'before_cursor_execute', lambda c, cu, s, p, co, e: statements.append(s))
        assert repo.count_canonical(pid) == 53
        page = repo.list_canonical_page(pid, limit=999)
        assert len(page) == 50
        assert page[0]['title'].startswith('000') and page[1]['title'].startswith('002')
        assert set(page[0]) == {'title', 'source', 'channel', 'published_at', 'canonical_url'}
        assert len(page[0]['title']) == len(page[0]['source']) == 300
        assert len(repo.list_canonical_page(pid, offset=50)) == 3
        assert repo.list_canonical_page(pid, limit=0) == []
        assert repo.count_canonical(other) == 0
        assert evidence.count_by_project(pid) == 1 and evidence.count_by_project(other) == 0
        assert not any('documents.body' in s or 'documents.metadata' in s for s in statements)
