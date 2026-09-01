"""Analytics snapshot contracts for AIPORG 2.0."""

from math import isfinite

from pydantic import JsonValue, field_validator

from app.schemas.common import ProjectId, SchemaBase, VersionedRunSchema


def _is_json_compatible(value: object) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return isfinite(value)
    if isinstance(value, list):
        return all(_is_json_compatible(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_compatible(item)
            for key, item in value.items()
        )
    return False


class AnalyticsSnapshotSchema(SchemaBase):
    project_id: ProjectId
    run: VersionedRunSchema
    metrics: dict[str, JsonValue]

    @field_validator("metrics", mode="before")
    @classmethod
    def validate_metrics_json_boundary(cls, value: object) -> object:
        if not isinstance(value, dict) or not _is_json_compatible(value):
            raise ValueError("metrics must contain only JSON-compatible values")
        return value


AnalyticsSnapshotRead = AnalyticsSnapshotSchema
