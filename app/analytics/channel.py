"""Unique-document channel analytics."""

from collections import Counter
from collections.abc import Sequence

from app.schemas.analytics import AnalyticsSnapshotSchema
from app.schemas.common import ProjectId, VersionedRunSchema
from app.schemas.document import CleanDocument


class ChannelAnalyticsService:
    """Calculate channel counts from cleaned unique-document records."""

    def build(
        self,
        project_id: ProjectId,
        run: VersionedRunSchema,
        documents: Sequence[CleanDocument],
    ) -> AnalyticsSnapshotSchema:
        counts = Counter(
            document.channel.value
            for document in documents
            if document.channel is not None
        )
        return AnalyticsSnapshotSchema(
            project_id=project_id,
            run=run,
            metrics={
                "unique_documents": len(documents),
                "channel_mentions": dict(sorted(counts.items())),
                "unclassified_documents": sum(
                    document.channel is None for document in documents
                ),
            },
        )
