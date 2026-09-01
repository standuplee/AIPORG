"""Collection run contracts for AIPORG 2.0."""

from app.core.enums import ChannelType, CollectionRunStatus
from app.schemas.common import ProjectId, RunId, SchemaBase
from pydantic import AwareDatetime, model_validator


class CollectionRun(SchemaBase):
    id: RunId
    project_id: ProjectId
    channel: ChannelType
    query: str
    started_at: AwareDatetime
    completed_at: AwareDatetime | None = None
    status: CollectionRunStatus
    documents_found: int
    documents_saved: int
    error_count: int

    @model_validator(mode="after")
    def validate_completion_time_for_terminal_status(self) -> "CollectionRun":
        if (
            self.status
            in {CollectionRunStatus.COMPLETED, CollectionRunStatus.FAILED}
            and self.completed_at is None
        ):
            raise ValueError("completed_at is required for terminal collection runs")
        return self


CollectionRunRead = CollectionRun
