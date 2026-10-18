from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.schemas.analytics import AnalyticsSnapshotSchema
from app.schemas.common import VersionedRunSchema
from app.visualization.service import (
    CHANNEL_DONUT_SLOT,
    TOP10_KEYWORDS_SLOT,
    VisualizationRenderError,
    VisualizationRenderService,
)

NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)


def _run() -> VersionedRunSchema:
    return VersionedRunSchema(run_id=uuid4(), input_version="v1", output_version="v1", created_at=NOW)


def _snapshot(**metrics: object) -> AnalyticsSnapshotSchema:
    return AnalyticsSnapshotSchema(
        project_id=uuid4(),
        run=VersionedRunSchema(run_id=uuid4(), input_version="v1", output_version="v1", created_at=NOW),
        metrics=metrics,
    )


def test_channel_donut_copies_counts_verbatim_and_sets_grounding_path() -> None:
    project_id = uuid4()
    snapshot = _snapshot(channel_mentions={"NEWS": 12, "VIDEO": 3})
    output = VisualizationRenderService().render_channel_donut(project_id, _run(), snapshot)

    assert output.slot_key == CHANNEL_DONUT_SLOT
    assert output.analytics_run_id == snapshot.run.run_id
    by_label = {item.label: item for item in output.items}
    assert by_label["NEWS"].value == 12
    assert by_label["NEWS"].analytics_path == "metrics.channel_mentions.NEWS"
    assert by_label["VIDEO"].value == 3
    assert output.approved is False


def test_channel_donut_requires_the_metric() -> None:
    snapshot = _snapshot(unrelated=1)
    with pytest.raises(VisualizationRenderError):
        VisualizationRenderService().render_channel_donut(uuid4(), _run(), snapshot)


def test_channel_donut_applies_presentation_overrides_without_changing_value() -> None:
    snapshot = _snapshot(channel_mentions={"NEWS": 12})
    output = VisualizationRenderService().render_channel_donut(
        uuid4(), _run(), snapshot,
        overrides={"NEWS": {"label": "뉴스", "color": "#ff0000", "order": 5, "included": False}},
    )
    item = output.items[0]
    assert item.label == "뉴스"
    assert item.value == 12  # unchanged despite override not containing "value"
    assert item.color == "#ff0000"
    assert item.order == 5
    assert item.included is False


def test_top10_keywords_ranks_by_count_desc_then_keyword_asc() -> None:
    snapshot = _snapshot(keyword_frequencies={
        "가나": 3, "다라": 9, "마바": 9, "사아": 1,
    })
    output = VisualizationRenderService().render_top10_keywords(uuid4(), _run(), snapshot)

    assert output.slot_key == TOP10_KEYWORDS_SLOT
    assert [item.label for item in output.items] == ["다라", "마바", "가나", "사아"]
    assert [item.order for item in output.items] == [0, 1, 2, 3]


def test_top10_keywords_truncates_to_ten() -> None:
    frequencies = {f"키워드{i}": i for i in range(1, 16)}
    snapshot = _snapshot(keyword_frequencies=frequencies)
    output = VisualizationRenderService().render_top10_keywords(uuid4(), _run(), snapshot)
    assert len(output.items) == 10
    assert output.items[0].label == "키워드15"


def test_top10_keywords_requires_the_metric() -> None:
    snapshot = _snapshot(unrelated=1)
    with pytest.raises(VisualizationRenderError):
        VisualizationRenderService().render_top10_keywords(uuid4(), _run(), snapshot)
