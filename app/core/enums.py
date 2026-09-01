from enum import Enum


class WorkflowState(str, Enum):
    CREATED = "created"
    QUERIES_READY = "queries_ready"
    COLLECTION_RUNNING = "collection_running"
    COLLECTION_COMPLETED = "collection_completed"
    CLEANING_COMPLETED = "cleaning_completed"
    EVIDENCE_COMPLETED = "evidence_completed"
    ISSUES_COMPLETED = "issues_completed"
    ANALYTICS_COMPLETED = "analytics_completed"
    NARRATIVE_COMPLETED = "narrative_completed"
    VISUALS_COMPLETED = "visuals_completed"
    REPORT_COMPLETED = "report_completed"


class CollectionRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FactStatus(str, Enum):
    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    UNCERTAIN = "UNCERTAIN"
    REJECTED = "REJECTED"


class ChannelType(str, Enum):
    NEWS = "news"
    BLOG = "blog"
    COMMUNITY = "community"
    SOCIAL = "social"
    VIDEO = "video"


class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class ConfidenceGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
