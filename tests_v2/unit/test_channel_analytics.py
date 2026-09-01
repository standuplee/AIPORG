from datetime import datetime, timezone
from uuid import uuid4

from app.analytics.channel import ChannelAnalyticsService
from app.core.enums import ChannelType
from app.schemas.common import VersionedRunSchema
from app.schemas.document import CleanDocument


def clean(channel: ChannelType) -> CleanDocument:
    return CleanDocument(
        document_id=uuid4(),
        title="제목",
        body="본문",
        canonical_url=f"https://example.test/{uuid4()}",
        cleaned_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
        channel=channel,
    )


def test_channel_analytics_counts_only_documents_with_channel_context() -> None:
    project_id = uuid4()
    run = VersionedRunSchema(
        run_id=uuid4(),
        input_version="cleaning:v1",
        output_version="analytics:v1",
        created_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
    )

    snapshot = ChannelAnalyticsService().build(
        project_id,
        run,
        [clean(ChannelType.NEWS), clean(ChannelType.NEWS), clean(ChannelType.BLOG)],
    )

    assert snapshot.metrics == {
        "unique_documents": 3,
        "channel_mentions": {"news": 2, "blog": 1},
        "unclassified_documents": 0,
    }
