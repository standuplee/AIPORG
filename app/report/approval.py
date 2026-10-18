"""Final report approval gate.

Implements the decision in docs/aiporg2/visualization-design.md: a Report
row is only ever created once the latest narrative output and every required
visualization slot are individually approved. No new schema fields are
needed on Report/VisualizationAsset for this -- the Report row's existence
*is* the approval record. This module only orchestrates existing
repositories; it makes no direct DB writes, no web requests, and no LLM
calls.
"""

from datetime import datetime
from uuid import uuid4

from app.repositories.narrative import NarrativeRepository
from app.repositories.report import ReportRepository
from app.repositories.visualization import VisualizationRepository
from app.schemas.common import ProjectId, VersionedRunSchema
from app.schemas.report import ReportRead, ReportSchema
from app.schemas.visualization import VisualizationAssetSchema
from app.visualization.service import CHANNEL_DONUT_SLOT, TOP10_KEYWORDS_SLOT

REQUIRED_VISUALIZATION_SLOTS = (CHANNEL_DONUT_SLOT, TOP10_KEYWORDS_SLOT)


class ReportApprovalError(ValueError):
    """Raised when the project is missing a required approval.

    ``missing`` names each blocking item ("narrative" or a visualization
    slot_key) so the caller can show the user exactly what is left.
    """

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"not all required approvals are in place: {missing}")


class ReportApprovalService:
    def __init__(
        self,
        narrative_repo: NarrativeRepository,
        visualization_repo: VisualizationRepository,
        report_repo: ReportRepository,
    ) -> None:
        self._narrative_repo = narrative_repo
        self._visualization_repo = visualization_repo
        self._report_repo = report_repo

    def approve(self, project_id: ProjectId, *, now: datetime) -> ReportRead:
        missing = []

        narrative_output = self._narrative_repo.get_latest_output(project_id)
        if narrative_output is None or not narrative_output.approved:
            missing.append("narrative")

        context = self._narrative_repo.get_latest(project_id)
        if context is None:
            missing.append("narrative")

        slot_outputs = {}
        for slot_key in REQUIRED_VISUALIZATION_SLOTS:
            output = self._visualization_repo.get_latest_output(project_id, slot_key)
            if output is None or not output.approved:
                missing.append(slot_key)
            else:
                slot_outputs[slot_key] = output

        if missing:
            raise ReportApprovalError(missing)

        assert context is not None
        visualizations = [
            self._visualization_repo.create(VisualizationAssetSchema(
                visualization_id=uuid4(),
                project_id=project_id,
                kind=output.kind,
                title=output.title,
                created_at=now,
            ))
            for output in slot_outputs.values()
        ]

        report = ReportSchema(
            report_id=uuid4(),
            project_id=project_id,
            run=VersionedRunSchema(
                run_id=uuid4(),
                input_version="report-approval:v1",
                output_version="report-approval:v1",
                created_at=now,
            ),
            context=context,
            visualizations=visualizations,
        )
        return self._report_repo.create(report)
