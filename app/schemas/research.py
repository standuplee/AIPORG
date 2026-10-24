"""Contracts for issue-driven research planning."""

from collections import Counter
from datetime import date
from enum import Enum

from pydantic import Field, model_validator

from app.schemas.common import SchemaBase


class QueryType(str, Enum):
    FACT = "FACT"
    DETAIL = "DETAIL"
    BACKGROUND = "BACKGROUND"
    IMPACT = "IMPACT"
    CONCERN = "CONCERN"
    REACTION = "REACTION"
    FOLLOWUP = "FOLLOWUP"


class SearchPurpose(str, Enum):
    FACT_RESEARCH = "FACT_RESEARCH"
    OPINION_CORPUS = "OPINION_CORPUS"
    FRAME_DISCOVERY = "FRAME_DISCOVERY"


class IssueInput(SchemaBase):
    region: str = Field(min_length=1)
    start_date: date
    end_date: date
    issue: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_period(self) -> "IssueInput":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class ResearchQuestion(SchemaBase):
    id: str = Field(min_length=1)
    type: QueryType
    question: str = Field(min_length=1)


class SearchQuery(SchemaBase):
    research_question_id: str = Field(min_length=1)
    type: QueryType
    query: str = Field(min_length=1)
    search_purpose: SearchPurpose


class IssueDecomposition(SchemaBase):
    subjects: list[str]
    actions: list[str]
    amounts: list[str]
    locations: list[str]
    organizations: list[str]
    policies: list[str]
    explicit_in_input: list[str]
    unknowns: list[str]
    persons: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    laws: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)


class QueryDraft(SchemaBase):
    """Qwen #2 output: lexical query variants for one research question."""

    research_question_id: str = Field(min_length=1)
    queries: list[str] = Field(min_length=1, max_length=3)


class QueryDraftSet(SchemaBase):
    drafts: list[QueryDraft]


_QUESTION_MIX = Counter(
    {
        "FACT": 2,
        "DETAIL": 2,
        "BACKGROUND": 1,
        "IMPACT": 2,
        "CONCERN": 2,
        "REACTION": 1,
        "FOLLOWUP": 1,
    }
)


def _validate_questions(questions: list[ResearchQuestion]) -> None:
    if Counter(question.type.value for question in questions) != _QUESTION_MIX:
        raise ValueError("research questions must match the required 11 question types")
    if len({question.id for question in questions}) != len(questions):
        raise ValueError("research question ids must be unique")


class ResearchPlan(SchemaBase):
    """Qwen #1 output: decomposition and research questions, no search queries."""

    decomposition: IssueDecomposition
    research_questions: list[ResearchQuestion] = Field(min_length=11, max_length=11)

    @model_validator(mode="after")
    def validate_questions(self) -> "ResearchPlan":
        _validate_questions(self.research_questions)
        return self


class QueryExpansionResult(SchemaBase):
    issue: str = Field(min_length=1)
    decomposition: IssueDecomposition
    protected_terms: list[str] = Field(default_factory=list)
    research_questions: list[ResearchQuestion] = Field(min_length=11, max_length=11)
    queries: list[SearchQuery] = Field(min_length=11)

    @model_validator(mode="after")
    def validate_query_links(self) -> "QueryExpansionResult":
        _validate_questions(self.research_questions)
        questions = {question.id: question for question in self.research_questions}
        if set(query.research_question_id for query in self.queries) != set(questions):
            raise ValueError("each research question must have at least one search query")
        normalized_queries = [" ".join(query.query.casefold().split()) for query in self.queries]
        if len(normalized_queries) != len(set(normalized_queries)):
            raise ValueError("duplicate search queries are not allowed")
        for query in self.queries:
            if query.type != questions[query.research_question_id].type:
                raise ValueError("query type must match its research question type")
        return self
