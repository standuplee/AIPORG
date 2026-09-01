"""Fact repository protocol."""

from typing import Protocol

from app.repositories.base import SessionScopedRepository
from app.schemas.common import ProjectId
from app.schemas.fact import FactId, FactRead, FactSchema, NumericFactSchema


class FactRepository(SessionScopedRepository, Protocol):
    """Persist facts with evidence-backed numeric facts."""

    def save_batch(self, project_id: ProjectId, facts: list[FactSchema]) -> list[FactRead]:
        """Persist a batch of qualitative facts for a project."""

    def save_numeric(
        self, project_id: ProjectId, fact_id: FactId, fact: NumericFactSchema
    ) -> NumericFactSchema:
        """Persist an evidence-backed numeric fact linked to a fact."""

    def get(self, project_id: ProjectId, fact_id: FactId) -> FactRead | None:
        """Return a fact when it exists for the project."""
