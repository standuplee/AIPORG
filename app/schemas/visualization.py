"""Visualization asset contracts for AIPORG 2.0.

The output contracts below (``VisualizationItemSchema``,
``VisualizationOutputSchema``) implement the decision in
``docs/aiporg2/visualization-design.md`` (2026-10-18): an editable,
analytics-grounded visualization version that can be previewed, edited, and
individually approved before a report bundles it. They are additive --
``VisualizationAssetSchema`` and its field names are unchanged, and it keeps
acting as the lightweight identifier a ``ReportSchema`` references.
"""

from typing import TypeAlias
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.schemas.common import ProjectId, RunId, SchemaBase, VersionedRunSchema


VisualizationId: TypeAlias = UUID


class VisualizationAssetSchema(SchemaBase):
    visualization_id: VisualizationId
    project_id: ProjectId
    kind: str
    title: str
    created_at: AwareDatetime


VisualizationAssetRead = VisualizationAssetSchema


class VisualizationItemSchema(SchemaBase):
    """One grounded row/segment of a visualization (a channel's donut slice,
    a TOP10 card). ``value`` is read verbatim from an AnalyticsSnapshot --
    never user-typed -- so it must carry the metrics path it came from.
    ``label``/``category``/``color``/``order``/``included`` are the only
    user-editable fields (requirements doc section 8.1)."""

    label: str
    value: int = Field(ge=0)
    analytics_path: str
    category: str | None = None
    color: str | None = None
    order: int
    included: bool = True

    @field_validator("analytics_path")
    @classmethod
    def validate_analytics_path(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("analytics_path cannot be empty")
        return value

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("label cannot be empty")
        return value


class VisualizationOutputSchema(SchemaBase):
    """One visualization version: a render, a user edit, or a regeneration.
    Every edit is a new version (a new ``run``); none overwrite a prior one.
    ``slot_key`` identifies which visualization this is (a project can have
    several, unlike narrative output which is one stream per project)."""

    project_id: ProjectId
    run: VersionedRunSchema
    analytics_run_id: RunId
    slot_key: str
    kind: str
    title: str
    items: list[VisualizationItemSchema]
    approved: bool = False
    approved_at: AwareDatetime | None = None

    @field_validator("slot_key", "kind", "title")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field cannot be empty")
        return value

    @model_validator(mode="after")
    def validate_approval_timestamp(self) -> "VisualizationOutputSchema":
        if self.approved and self.approved_at is None:
            raise ValueError("approved output must carry approved_at")
        if not self.approved and self.approved_at is not None:
            raise ValueError("unapproved output must not carry approved_at")
        return self


VisualizationOutputRead = VisualizationOutputSchema
