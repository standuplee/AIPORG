from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.common import VersionedRunSchema
from app.schemas.visualization import VisualizationItemSchema, VisualizationOutputSchema


NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)


def _run() -> VersionedRunSchema:
    return VersionedRunSchema(run_id=uuid4(), input_version="v1", output_version="v1", created_at=NOW)


def _item(**overrides: object) -> VisualizationItemSchema:
    defaults: dict[str, object] = {
        "label": "뉴스",
        "value": 12,
        "analytics_path": "metrics.channel_mentions.NEWS",
        "order": 0,
    }
    defaults.update(overrides)
    return VisualizationItemSchema.model_validate(defaults)


def test_item_requires_non_empty_analytics_path() -> None:
    with pytest.raises(ValidationError):
        _item(analytics_path="")


def test_item_requires_non_empty_label() -> None:
    with pytest.raises(ValidationError):
        _item(label="   ")


def test_item_rejects_negative_value() -> None:
    with pytest.raises(ValidationError):
        _item(value=-1)


def test_output_defaults_to_unapproved() -> None:
    output = VisualizationOutputSchema(
        project_id=uuid4(),
        run=_run(),
        analytics_run_id=uuid4(),
        slot_key="channel_donut",
        kind="chart",
        title="채널 비중",
        items=[_item()],
    )
    assert output.approved is False
    assert output.approved_at is None


def test_output_approved_requires_timestamp() -> None:
    with pytest.raises(ValidationError, match="approved_at"):
        VisualizationOutputSchema(
            project_id=uuid4(),
            run=_run(),
            analytics_run_id=uuid4(),
            slot_key="channel_donut",
            kind="chart",
            title="채널 비중",
            items=[_item()],
            approved=True,
        )


def test_output_unapproved_rejects_timestamp() -> None:
    with pytest.raises(ValidationError, match="approved_at"):
        VisualizationOutputSchema(
            project_id=uuid4(),
            run=_run(),
            analytics_run_id=uuid4(),
            slot_key="channel_donut",
            kind="chart",
            title="채널 비중",
            items=[_item()],
            approved=False,
            approved_at=NOW,
        )


def test_output_approved_with_timestamp_is_valid() -> None:
    output = VisualizationOutputSchema(
        project_id=uuid4(),
        run=_run(),
        analytics_run_id=uuid4(),
        slot_key="channel_donut",
        kind="chart",
        title="채널 비중",
        items=[_item()],
        approved=True,
        approved_at=NOW,
    )
    assert output.approved is True
    assert output.approved_at == NOW


def test_output_rejects_empty_slot_key() -> None:
    with pytest.raises(ValidationError):
        VisualizationOutputSchema(
            project_id=uuid4(),
            run=_run(),
            analytics_run_id=uuid4(),
            slot_key="  ",
            kind="chart",
            title="채널 비중",
            items=[_item()],
        )


def test_output_allows_empty_items_list() -> None:
    output = VisualizationOutputSchema(
        project_id=uuid4(),
        run=_run(),
        analytics_run_id=uuid4(),
        slot_key="channel_donut",
        kind="chart",
        title="채널 비중",
        items=[],
    )
    assert output.items == []
