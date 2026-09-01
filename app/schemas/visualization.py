"""Visualization asset contracts for AIPORG 2.0."""

from typing import TypeAlias
from uuid import UUID

from pydantic import AwareDatetime

from app.schemas.common import ProjectId, SchemaBase


VisualizationId: TypeAlias = UUID


class VisualizationAssetSchema(SchemaBase):
    visualization_id: VisualizationId
    project_id: ProjectId
    kind: str
    title: str
    created_at: AwareDatetime


VisualizationAssetRead = VisualizationAssetSchema
