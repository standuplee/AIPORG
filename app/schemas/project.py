"""Project-level contracts for AIPORG 2.0."""

from app.core.enums import ChannelType, WorkflowState
from app.schemas.common import (
    AnalysisPeriodSchema,
    ComparisonPeriodSchema,
    ProjectId,
    SchemaBase,
    TargetSchema,
)


class ProjectCreate(SchemaBase):
    name: str
    target: TargetSchema
    analysis_period: AnalysisPeriodSchema
    comparison_period: ComparisonPeriodSchema
    channels: list[ChannelType]


class ProjectRead(ProjectCreate):
    project_id: ProjectId


class ProjectWorkflowSnapshot(SchemaBase):
    project_id: ProjectId
    workflow_state: WorkflowState
