"""Repository contracts for AIPORG 2.0 persistence boundaries."""

from app.repositories.analytics import AnalyticsRepository
from app.repositories.base import SessionScopedRepository
from app.repositories.collection import CollectionRunRepository, QuerySetRepository
from app.repositories.document import DocumentRepository
from app.repositories.duplicate_cluster import DuplicateClusterRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.fact import FactRepository
from app.repositories.issue import IssueRepository
from app.repositories.narrative import NarrativeRepository
from app.repositories.project import ProjectRepository
from app.repositories.report import ReportRepository
from app.repositories.visualization import VisualizationRepository

__all__ = [
    "AnalyticsRepository",
    "CollectionRunRepository",
    "DocumentRepository",
    "DuplicateClusterRepository",
    "EvidenceRepository",
    "FactRepository",
    "IssueRepository",
    "NarrativeRepository",
    "ProjectRepository",
    "QuerySetRepository",
    "ReportRepository",
    "SessionScopedRepository",
    "VisualizationRepository",
]
