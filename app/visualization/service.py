"""Deterministic visualization rendering from AnalyticsSnapshot metrics.

No network access, no LLM calls (AGENTS.md rule 5 applies to Analyzer; this
module only reads an already-computed snapshot, the same boundary
AnalyticsService itself sits behind). Every ``value`` on a rendered item is
copied verbatim from ``snapshot.metrics`` -- this service never invents or
edits a count (AGENTS.md rule 7). Only presentation fields (label, category,
color, order, included) can be overridden by the caller.
"""

from app.schemas.analytics import AnalyticsSnapshotSchema
from app.schemas.common import ProjectId, VersionedRunSchema
from app.schemas.visualization import VisualizationItemSchema, VisualizationOutputSchema

CHANNEL_DONUT_SLOT = "channel_donut"
TOP10_KEYWORDS_SLOT = "top10_keywords"

ItemOverride = dict[str, object]


class VisualizationRenderError(ValueError):
    """Raised when the analytics snapshot lacks a metric this visualization needs."""


class VisualizationRenderService:
    """Builds VIS-02 (channel donut) and VIS-07 (TOP10 keyword cards)."""

    def render_channel_donut(
        self,
        project_id: ProjectId,
        run: VersionedRunSchema,
        snapshot: AnalyticsSnapshotSchema,
        *,
        title: str = "채널 비중",
        overrides: dict[str, ItemOverride] | None = None,
    ) -> VisualizationOutputSchema:
        channel_mentions = snapshot.metrics.get("channel_mentions")
        if not isinstance(channel_mentions, dict):
            raise VisualizationRenderError("snapshot is missing metrics.channel_mentions")
        items = self._build_items(
            {channel: count for channel, count in channel_mentions.items()},
            path_prefix="metrics.channel_mentions",
            overrides=overrides,
        )
        return VisualizationOutputSchema(
            project_id=project_id,
            run=run,
            analytics_run_id=snapshot.run.run_id,
            slot_key=CHANNEL_DONUT_SLOT,
            kind="chart",
            title=title,
            items=items,
        )

    def render_top10_keywords(
        self,
        project_id: ProjectId,
        run: VersionedRunSchema,
        snapshot: AnalyticsSnapshotSchema,
        *,
        title: str = "TOP10 키워드",
        overrides: dict[str, ItemOverride] | None = None,
    ) -> VisualizationOutputSchema:
        keyword_frequencies = snapshot.metrics.get("keyword_frequencies")
        if not isinstance(keyword_frequencies, dict):
            raise VisualizationRenderError("snapshot is missing metrics.keyword_frequencies")
        ranked = sorted(
            keyword_frequencies.items(), key=lambda pair: (-pair[1], pair[0])
        )[:10]
        items = self._build_items(
            dict(ranked),
            path_prefix="metrics.keyword_frequencies",
            overrides=overrides,
            preserve_rank_order=True,
        )
        return VisualizationOutputSchema(
            project_id=project_id,
            run=run,
            analytics_run_id=snapshot.run.run_id,
            slot_key=TOP10_KEYWORDS_SLOT,
            kind="cards",
            title=title,
            items=items,
        )

    @staticmethod
    def _build_items(
        counts: dict[str, int],
        *,
        path_prefix: str,
        overrides: dict[str, ItemOverride] | None,
        preserve_rank_order: bool = False,
    ) -> list[VisualizationItemSchema]:
        overrides = overrides or {}
        keys = list(counts) if preserve_rank_order else sorted(counts)
        items = []
        for order, key in enumerate(keys):
            override = overrides.get(key, {})
            items.append(VisualizationItemSchema(
                label=str(override.get("label", key)),
                value=counts[key],
                analytics_path=f"{path_prefix}.{key}",
                category=override.get("category"),
                color=override.get("color"),
                order=int(override.get("order", order)),
                included=bool(override.get("included", True)),
            ))
        return items
