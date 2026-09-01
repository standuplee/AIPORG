"""AIPORG 2.0 SQLAlchemy model registry."""

from app.models.analytics import AnalyticsSnapshot
from app.models.base import Base
from app.models.collection import CollectionRun
from app.models.document import Document, DocumentDuplicate, DuplicateCluster
from app.models.evidence import Evidence, EvidenceDocument
from app.models.fact import Fact, NumericFact, NumericFactEvidence
from app.models.issue import Issue, IssueFact, IssueSubissue
from app.models.narrative import Narrative
from app.models.project import Project, Query, QuerySet
from app.models.report import Report, ReportVisualization
from app.models.visualization import Visualization

__all__ = [
    "AnalyticsSnapshot",
    "Base",
    "CollectionRun",
    "Document",
    "DocumentDuplicate",
    "DuplicateCluster",
    "Evidence",
    "EvidenceDocument",
    "Fact",
    "Issue",
    "IssueFact",
    "IssueSubissue",
    "Narrative",
    "NumericFact",
    "NumericFactEvidence",
    "Project",
    "Query",
    "QuerySet",
    "Report",
    "ReportVisualization",
    "Visualization",
]
