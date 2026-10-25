"""Human review of reaction candidates: every candidate must be approved or rejected before analysis."""

import json
from enum import Enum
from pathlib import Path

from app.schemas.common import SchemaBase
from app.schemas.research import IssueInput
from app.search.documents import FactResearchResult
from pydantic import Field

from app.search.opinion import OpinionCandidates


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ReviewSession(SchemaBase):
    issue: IssueInput
    candidates: OpinionCandidates
    fact: FactResearchResult
    fact_sources: dict[str, list[str]]  # result_id -> [title, url] for the fact section's citations
    statuses: dict[str, ReviewStatus]  # one decision per reaction candidate
    topic_selected: dict[str, bool] = Field(default_factory=dict)  # discussion topics start selected; unticking drops one

    def selected_topic_ids(self) -> set[str]:
        return {i for i, keep in self.topic_selected.items() if keep}

    def counts(self) -> dict[str, int]:
        values = list(self.statuses.values())
        return {s.value: values.count(s) for s in ReviewStatus}

    def all_reviewed(self) -> bool:
        return ReviewStatus.PENDING.value not in {s.value for s in self.statuses.values()}

    def approved_ids(self) -> set[str]:
        return {i for i, s in self.statuses.items() if s is ReviewStatus.APPROVED}


def new_session(issue: IssueInput, candidates: OpinionCandidates, fact: FactResearchResult, fact_sources: dict[str, list[str]]) -> ReviewSession:
    # Nothing is pre-approved: Qwen's own verdict is a suggestion, not a decision.
    return ReviewSession(issue=issue, candidates=candidates, fact=fact, fact_sources=fact_sources,
                         statuses={c.result_id: ReviewStatus.PENDING for c in candidates.candidates},
                         topic_selected={t.topic_id: True for t in candidates.topics})


def save_session(path: Path, session: ReviewSession) -> None:
    path.write_text(session.model_dump_json(indent=2), encoding="utf-8")


def load_session(path: Path) -> ReviewSession:
    return ReviewSession.model_validate(json.loads(path.read_text(encoding="utf-8")))


def set_status(path: Path, result_id: str, status: ReviewStatus) -> ReviewSession:
    """Re-reads the file first so two browser tabs cannot overwrite each other's decisions."""
    session = load_session(path)
    if result_id not in session.statuses:
        raise KeyError(result_id)
    session.statuses[result_id] = status
    save_session(path, session)
    return session


def set_topic(path: Path, topic_id: str, selected: bool) -> ReviewSession:
    session = load_session(path)
    if topic_id not in session.topic_selected:
        raise KeyError(topic_id)
    session.topic_selected[topic_id] = selected
    save_session(path, session)
    return session
