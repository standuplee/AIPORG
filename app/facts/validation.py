"""Evidence-backed fact status validation without claim generation."""

from app.core.enums import ConfidenceGrade, FactStatus
from app.schemas.fact import FactSchema


class FactValidationService:
    """Validate fact provenance and assign only evidence-backed status."""

    def validate(self, fact: FactSchema, *, official_source: bool = False) -> FactSchema:
        if not fact.evidence_document_ids:
            raise ValueError("fact evidence is required")
        if official_source:
            status = FactStatus.VERIFIED
            confidence = ConfidenceGrade.A
        elif fact.source_count >= 2:
            status = FactStatus.VERIFIED
            confidence = fact.confidence
        else:
            status = FactStatus.SUPPORTED
            confidence = fact.confidence
        return fact.model_copy(update={"status": status, "confidence": confidence})
