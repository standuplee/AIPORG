from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.enums import ChannelType, CollectionRunStatus
from app.schemas.collection import CollectionRun
from app.schemas.document import (
    CleanDocument,
    DuplicateClusterSchema,
    RawDocument,
    SearchResult,
)
from app.schemas.query import SearchQuery


def search_result_payload() -> dict[str, object]:
    return {
        "channel": ChannelType.NEWS,
        "source": "Naver News",
        "title": "Public opinion update",
        "published_at": "2026-08-14T09:00:00Z",
        "url": "https://news.example.com/articles/1",
        "query": "Chungnam public opinion",
    }


def raw_document_payload() -> dict[str, object]:
    return {
        "document_id": str(uuid4()),
        **search_result_payload(),
        "platform": "naver",
        "body": "The full article text.",
        "metadata": {"reporter": "Kim"},
        "collected_at": "2026-08-14T10:00:00Z",
    }


def clean_document_payload() -> dict[str, object]:
    return {
        "document_id": str(uuid4()),
        "title": "Public opinion update",
        "body": "The full article text.",
        "canonical_url": "https://news.example.com/articles/1",
        "cleaned_at": "2026-08-14T10:01:00Z",
    }


def test_query_and_collection_schema_contracts_use_existing_enums() -> None:
    assert set(SearchQuery.model_fields) == {"query", "channels"}
    assert set(CollectionRun.model_fields) == {
        "id",
        "project_id",
        "channel",
        "query",
        "started_at",
        "completed_at",
        "status",
        "documents_found",
        "documents_saved",
        "error_count",
    }

    query = SearchQuery.model_validate(
        {"query": "Chungnam public opinion", "channels": ["news", "blog"]}
    )
    run = CollectionRun.model_validate(
        {
            "id": str(uuid4()),
            "project_id": str(uuid4()),
            "channel": "news",
            "query": "Chungnam public opinion",
            "status": "completed",
            "started_at": "2026-08-14T09:00:00Z",
            "completed_at": "2026-08-14T10:00:00Z",
            "documents_found": 12,
            "documents_saved": 10,
            "error_count": 0,
        }
    )

    assert query.channels == [ChannelType.NEWS, ChannelType.BLOG]
    assert query.channels[0] is ChannelType.NEWS
    assert query.channels[1] is ChannelType.BLOG
    assert run.channel is ChannelType.NEWS
    assert run.status is CollectionRunStatus.COMPLETED


@pytest.mark.parametrize("status", [CollectionRunStatus.PENDING, CollectionRunStatus.RUNNING])
def test_collection_run_allows_non_terminal_statuses_without_completion_time(
    status: CollectionRunStatus,
) -> None:
    run = CollectionRun.model_validate(
        {
            "id": str(uuid4()),
            "project_id": str(uuid4()),
            "channel": "news",
            "query": "Chungnam public opinion",
            "status": status,
            "started_at": "2026-08-14T09:00:00Z",
            "documents_found": 0,
            "documents_saved": 0,
            "error_count": 0,
        }
    )

    assert run.completed_at is None


@pytest.mark.parametrize("status", [CollectionRunStatus.COMPLETED, CollectionRunStatus.FAILED])
def test_collection_run_requires_completion_time_for_terminal_statuses(
    status: CollectionRunStatus,
) -> None:
    with pytest.raises(ValidationError, match="completed_at"):
        CollectionRun.model_validate(
            {
                "id": str(uuid4()),
                "project_id": str(uuid4()),
                "channel": "news",
                "query": "Chungnam public opinion",
                "status": status,
                "started_at": "2026-08-14T09:00:00Z",
                "documents_found": 0,
                "documents_saved": 0,
                "error_count": 0,
            }
        )


def test_collection_run_keeps_optional_completion_time_timezone_aware() -> None:
    run = CollectionRun.model_validate(
        {
            "id": str(uuid4()),
            "project_id": str(uuid4()),
            "channel": "news",
            "query": "Chungnam public opinion",
            "status": "running",
            "started_at": "2026-08-14T09:00:00Z",
            "completed_at": "2026-08-14T10:00:00+09:00",
            "documents_found": 0,
            "documents_saved": 0,
            "error_count": 0,
        }
    )

    assert run.completed_at == datetime(2026, 8, 14, 1, tzinfo=timezone.utc)
    assert run.completed_at.tzinfo is not None


@pytest.mark.parametrize(
    "schema,payload,naive_timestamp_fields",
    [
        (
            CollectionRun,
            {
                "id": str(uuid4()),
                "project_id": str(uuid4()),
                "channel": "news",
                "query": "Chungnam public opinion",
                "status": "completed",
                "started_at": "2026-08-14T09:00:00Z",
                "completed_at": "2026-08-14T10:00:00Z",
                "documents_found": 12,
                "documents_saved": 10,
                "error_count": 0,
            },
            ("started_at", "completed_at"),
        ),
        (SearchResult, search_result_payload(), ("published_at",)),
        (RawDocument, raw_document_payload(), ("published_at", "collected_at")),
        (CleanDocument, clean_document_payload(), ("cleaned_at",)),
    ],
)
def test_document_contract_schemas_reject_naive_datetimes(
    schema: type[object],
    payload: dict[str, object],
    naive_timestamp_fields: tuple[str, ...],
) -> None:
    for field in naive_timestamp_fields:
        naive_payload = {**payload, field: "2026-08-14T09:00:00"}

        with pytest.raises(ValidationError):
            schema.model_validate(naive_payload)  # type: ignore[attr-defined]


def test_channel_bearing_schemas_parse_channel_enum_members() -> None:
    query = SearchQuery.model_validate(
        {"query": "Chungnam public opinion", "channels": ["news", "blog"]}
    )
    run = CollectionRun.model_validate(
        {
            "id": str(uuid4()),
            "project_id": str(uuid4()),
            "channel": "news",
            "query": "Chungnam public opinion",
            "status": "completed",
            "started_at": "2026-08-14T09:00:00Z",
            "completed_at": "2026-08-14T10:00:00Z",
            "documents_found": 12,
            "documents_saved": 10,
            "error_count": 0,
        }
    )
    result = SearchResult.model_validate(search_result_payload())
    raw_document = RawDocument.model_validate(raw_document_payload())

    assert query.channels[0] is ChannelType.NEWS
    assert query.channels[1] is ChannelType.BLOG
    assert run.channel is ChannelType.NEWS
    assert result.channel is ChannelType.NEWS
    assert raw_document.channel is ChannelType.NEWS


@pytest.mark.parametrize(
    "schema,payload",
    [
        (SearchQuery, {"query": "Chungnam public opinion", "channels": ["invalid"]}),
        (CollectionRun, {
            "id": str(uuid4()),
            "project_id": str(uuid4()),
            "channel": "invalid",
            "query": "Chungnam public opinion",
            "status": "completed",
            "started_at": "2026-08-14T09:00:00Z",
            "completed_at": "2026-08-14T10:00:00Z",
            "documents_found": 12,
            "documents_saved": 10,
            "error_count": 0,
        }),
        (SearchResult, {**search_result_payload(), "channel": "invalid"}),
        (RawDocument, {**raw_document_payload(), "channel": "invalid"}),
    ],
)
def test_channel_bearing_schemas_reject_invalid_channels(
    schema: type[object], payload: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(payload)  # type: ignore[attr-defined]


def test_search_result_uses_exact_prd_field_names() -> None:
    assert set(SearchResult.model_fields) == {
        "source",
        "channel",
        "title",
        "url",
        "published_at",
        "query",
    }

    result = SearchResult.model_validate(search_result_payload())

    assert result.published_at == datetime(2026, 8, 14, 9, tzinfo=timezone.utc)
    assert result.query == "Chungnam public opinion"


def test_raw_document_requires_every_prd_field() -> None:
    required_fields = {
        "document_id",
        "channel",
        "platform",
        "source",
        "title",
        "body",
        "published_at",
        "url",
        "query",
        "metadata",
        "collected_at",
    }
    assert set(RawDocument.model_fields) == required_fields

    payload = raw_document_payload()
    for field in required_fields:
        incomplete_payload = {key: value for key, value in payload.items() if key != field}

        with pytest.raises(ValidationError, match="Field required"):
            RawDocument.model_validate(incomplete_payload)


def test_clean_document_uses_minimal_cleaned_document_fields() -> None:
    assert set(CleanDocument.model_fields) == {
        "document_id",
        "title",
        "body",
        "canonical_url",
        "cleaned_at",
        "source",
        "channel",
        "platform",
        "published_at",
        "query",
        "metadata",
    }

    document = CleanDocument.model_validate(
        clean_document_payload()
    )

    assert document.canonical_url == "https://news.example.com/articles/1"


def test_duplicate_cluster_schema_uses_exact_field_names() -> None:
    assert set(DuplicateClusterSchema.model_fields) == {
        "cluster_id",
        "canonical_document",
        "duplicates",
        "unique_sources",
        "distribution_count",
    }

    canonical_document = uuid4()
    duplicate_document_id = uuid4()
    cluster = DuplicateClusterSchema.model_validate(
        {
            "cluster_id": str(uuid4()),
            "canonical_document": str(canonical_document),
            "duplicates": [str(duplicate_document_id)],
            "unique_sources": ["Naver News"],
            "distribution_count": 2,
        }
    )

    assert cluster.canonical_document == canonical_document
    assert cluster.duplicates == [duplicate_document_id]


@pytest.mark.parametrize(
    "schema,payload",
    [
        (SearchQuery, {"query": "Chungnam", "channels": ["news"], "extra": True}),
        (CollectionRun, {
            "id": str(uuid4()),
            "project_id": str(uuid4()),
            "channel": "news",
            "query": "Chungnam public opinion",
            "status": "pending",
            "started_at": "2026-08-14T09:00:00Z",
            "completed_at": "2026-08-14T10:00:00Z",
            "documents_found": 0,
            "documents_saved": 0,
            "error_count": 0,
            "extra": True,
        }),
        (SearchResult, {**search_result_payload(), "extra": True}),
        (RawDocument, {**raw_document_payload(), "extra": True}),
        (CleanDocument, {**clean_document_payload(), "extra": True}),
        (DuplicateClusterSchema, {
            "cluster_id": str(uuid4()),
            "canonical_document": str(uuid4()),
            "duplicates": [],
            "unique_sources": [],
            "distribution_count": 1,
            "extra": True,
        }),
    ],
)
def test_document_contract_schemas_reject_extra_fields(
    schema: type[object], payload: dict[str, object]
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        schema.model_validate(payload)  # type: ignore[attr-defined]


def test_raw_document_does_not_alias_published_at() -> None:
    payload = raw_document_payload()
    published_at = payload.pop("published_at")
    payload["publishedAt"] = published_at

    with pytest.raises(ValidationError, match="Field required"):
        RawDocument.model_validate(payload)
