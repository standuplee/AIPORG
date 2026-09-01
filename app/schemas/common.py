"""Shared strict schemas for AIPORG 2.0 contracts."""

from datetime import date, datetime
from typing import TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


ProjectId: TypeAlias = UUID
RunId: TypeAlias = UUID


class SchemaBase(BaseModel):
    """Base class that keeps external contracts explicit."""

    model_config = ConfigDict(extra="forbid")


class PeriodSchema(SchemaBase):
    start: date
    end: date

    @model_validator(mode="after")
    def validate_date_order(self) -> "PeriodSchema":
        if self.start > self.end:
            raise ValueError("start must be on or before end")
        return self


class AnalysisPeriodSchema(PeriodSchema):
    pass


class ComparisonPeriodSchema(PeriodSchema):
    pass


class TargetSchema(SchemaBase):
    organization: str
    primary_person: str
    region: str


class VersionedRunSchema(SchemaBase):
    run_id: RunId
    input_version: str
    output_version: str
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def validate_created_at_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value
