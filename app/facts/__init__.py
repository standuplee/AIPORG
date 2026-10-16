"""Evidence-backed fact extraction and validation services."""

from app.facts.extraction import FactExtractionService
from app.facts.validation import FactValidationService

__all__ = ["FactExtractionService", "FactValidationService"]
