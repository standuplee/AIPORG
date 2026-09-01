"""Strict report aggregate contracts for AIPORG 2.0."""

from typing import TypeAlias
from uuid import UUID

from pydantic import model_validator

from app.schemas.common import ProjectId, SchemaBase, VersionedRunSchema
from app.schemas.narrative import NarrativeContext
from app.schemas.visualization import VisualizationAssetSchema


ReportId: TypeAlias = UUID


class ReportSchema(SchemaBase):
    report_id: ReportId
    project_id: ProjectId
    run: VersionedRunSchema
    context: NarrativeContext
    visualizations: list[VisualizationAssetSchema]

    @model_validator(mode="after")
    def validate_visualization_projects(self) -> "ReportSchema":
        if any(
            visualization.project_id != self.project_id
            for visualization in self.visualizations
        ):
            raise ValueError("visualization project_id must match report project_id")
        return self


ReportRead = ReportSchema
