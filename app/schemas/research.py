"""Contracts for issue-driven research planning."""

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
    purpose: str = Field(min_length=1)


class QueryExpansionResult(SchemaBase):
    issue: str = Field(min_length=1)
    protected_entities: list[str] = Field(default_factory=list)
    research_questions: list[ResearchQuestion] = Field(min_length=1, max_length=10)
    queries: list[SearchQuery] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_query_links(self) -> "QueryExpansionResult":
        questions = {question.id: question for question in self.research_questions}
        if len(questions) != len(self.research_questions):
            raise ValueError("research question ids must be unique")
        query_question_ids = {query.research_question_id for query in self.queries}
        if set(questions) != query_question_ids:
            raise ValueError("every research question must have at least one search query")
        for query in self.queries:
            question = questions.get(query.research_question_id)
            if question is None:
                raise ValueError("every query must reference a research question")
            if query.type != question.type:
                raise ValueError("query type must match its research question type")
        return self
