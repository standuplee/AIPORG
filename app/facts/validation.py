"""Evidence-backed fact status and numeric-value validation."""

import math
import re
from collections.abc import Mapping
from uuid import UUID

from app.core.enums import ConfidenceGrade, FactStatus
from app.schemas.evidence import EvidenceSchema
from app.schemas.fact import FactSchema, NumericFactSchema


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

    def validate_numeric(
        self,
        fact: NumericFactSchema,
        *,
        evidence_by_id: Mapping[UUID, EvidenceSchema],
    ) -> NumericFactSchema:
        excerpts = []
        for evidence_id in fact.evidence_ids:
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                raise ValueError("numeric fact references unknown evidence")
            excerpts.append(evidence.excerpt)
        supported_values = {
            float(token.replace(",", ""))
            for excerpt in excerpts
            for token in re.findall(r"(?<![\w.])[+-]?\d[\d,]*(?:\.\d+)?", excerpt)
        }
        if not any(math.isclose(fact.value, value) for value in supported_values):
            raise ValueError("numeric value is not present in linked evidence")
        return fact
