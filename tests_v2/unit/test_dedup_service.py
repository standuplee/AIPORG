from uuid import uuid4

from app.dedup.service import DeduplicationService
from app.schemas.document import CleanDocument


def clean(document_id, *, url: str, title: str, body: str) -> CleanDocument:
    from datetime import datetime, timezone

    return CleanDocument(
        document_id=document_id,
        title=title,
        body=body,
        canonical_url=url,
        cleaned_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )


def test_dedup_clusters_url_title_and_body_duplicates() -> None:
    first = uuid4()
    second = uuid4()
    third = uuid4()
    fourth = uuid4()
    fifth = uuid4()
    sixth = uuid4()
    documents = [
        clean(first, url="https://example.test/1", title="첫 기사", body="본문 A"),
        clean(second, url="https://example.test/1", title="다른 제목", body="다른 본문"),
        clean(third, url="https://example.test/3", title="같은 제목", body="본문 C"),
        clean(fourth, url="https://example.test/4", title="같은 제목", body="본문 D"),
        clean(fifth, url="https://example.test/5", title="다섯 번째", body="본문 E"),
        clean(sixth, url="https://example.test/6", title="여섯 번째", body="본문 E"),
    ]

    clusters = DeduplicationService().cluster(
        documents,
        source_by_document={
            first: "연합뉴스", second: "지역언론", third: "연합뉴스",
            fourth: "블로그", fifth: "연합뉴스", sixth: "블로그",
        },
    )

    assert len(clusters) == 3
    assert {frozenset([cluster.canonical_document, *cluster.duplicates]) for cluster in clusters} == {
        frozenset([first, second]), frozenset([third, fourth]), frozenset([fifth, sixth])
    }
    url_cluster = next(cluster for cluster in clusters if second in cluster.duplicates or cluster.canonical_document == second)
    assert url_cluster.unique_sources == ["연합뉴스", "지역언론"]
    assert url_cluster.distribution_count == 2


def test_dedup_is_order_independent_and_requires_provenance() -> None:
    first = uuid4()
    second = uuid4()
    documents = [
        clean(first, url="https://example.test/1", title="제목", body="본문"),
        clean(second, url="https://example.test/2", title="제목", body="다른 본문"),
    ]
    service = DeduplicationService()
    sources = {first: "연합뉴스", second: "지역언론"}

    forward = service.cluster(documents, source_by_document=sources)
    reverse = service.cluster(reversed(documents), source_by_document=sources)

    assert forward == reverse

    try:
        service.cluster(documents, source_by_document={first: "연합뉴스"})
    except ValueError as exc:
        assert "source" in str(exc)
    else:
        raise AssertionError("missing source provenance must be rejected")


def test_dedup_does_not_emit_singletons_and_is_stable() -> None:
    first = uuid4()
    second = uuid4()
    documents = [
        clean(first, url="https://example.test/1", title="제목", body="본문"),
        clean(second, url="https://example.test/2", title="다른 제목", body="다른 본문"),
    ]

    service = DeduplicationService()
    assert service.cluster(
        documents,
        source_by_document={first: "연합뉴스", second: "지역언론"},
    ) == []
