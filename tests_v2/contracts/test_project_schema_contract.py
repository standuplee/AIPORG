from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.enums import ChannelType, WorkflowState
from app.schemas.common import VersionedRunSchema
from app.schemas.project import ProjectCreate, ProjectRead, ProjectWorkflowSnapshot


def project_payload() -> dict[str, object]:
    return {
        "name": "Chungnam public opinion",
        "target": {
            "organization": "Chungcheongnam-do",
            "primary_person": "Governor",
            "region": "Chungcheongnam-do",
        },
        "analysis_period": {"start": "2026-07-01", "end": "2026-07-31"},
        "comparison_period": {"start": "2026-06-01", "end": "2026-06-30"},
        "channels": [ChannelType.NEWS, ChannelType.BLOG],
    }


def test_project_schema_contract_uses_exact_prd_field_names() -> None:
    assert set(ProjectCreate.model_fields) == {
        "name",
        "target",
        "analysis_period",
        "comparison_period",
        "channels",
    }
    assert set(ProjectRead.model_fields) == {"project_id", *ProjectCreate.model_fields}
    assert set(ProjectCreate.model_fields["target"].annotation.model_fields) == {
        "organization",
        "primary_person",
        "region",
    }
    assert set(ProjectCreate.model_fields["analysis_period"].annotation.model_fields) == {
        "start",
        "end",
    }
    assert set(ProjectCreate.model_fields["comparison_period"].annotation.model_fields) == {
        "start",
        "end",
    }


def test_project_read_accepts_prd_payload() -> None:
    project = ProjectRead.model_validate({"project_id": str(uuid4()), **project_payload()})

    assert project.name == "Chungnam public opinion"
    assert project.target.organization == "Chungcheongnam-do"
    assert project.target.primary_person == "Governor"
    assert project.target.region == "Chungcheongnam-do"
    assert project.analysis_period.start == date(2026, 7, 1)
    assert project.analysis_period.end == date(2026, 7, 31)
    assert project.comparison_period.start == date(2026, 6, 1)
    assert project.comparison_period.end == date(2026, 6, 30)
    assert project.channels == [ChannelType.NEWS, ChannelType.BLOG]


@pytest.mark.parametrize("required_field", ["name", "target", "analysis_period"])
def test_project_create_requires_prd_fields(required_field: str) -> None:
    payload = project_payload()
    payload.pop(required_field)

    with pytest.raises(ValidationError, match="Field required"):
        ProjectCreate.model_validate(payload)


def test_project_create_rejects_invalid_channel_enum() -> None:
    payload = {**project_payload(), "channels": ["podcast"]}

    with pytest.raises(ValidationError, match="Input should be"):
        ProjectCreate.model_validate(payload)


def test_project_read_serializes_to_prd_json_shape() -> None:
    project_id = uuid4()
    project = ProjectRead.model_validate({"project_id": project_id, **project_payload()})

    assert project.model_dump(mode="json") == {
        "project_id": str(project_id),
        "name": "Chungnam public opinion",
        "target": {
            "organization": "Chungcheongnam-do",
            "primary_person": "Governor",
            "region": "Chungcheongnam-do",
        },
        "analysis_period": {"start": "2026-07-01", "end": "2026-07-31"},
        "comparison_period": {"start": "2026-06-01", "end": "2026-06-30"},
        "channels": ["news", "blog"],
    }


@pytest.mark.parametrize("period_field", ["analysis_period", "comparison_period"])
def test_project_create_rejects_period_start_after_end(period_field: str) -> None:
    payload = project_payload()
    payload[period_field] = {"start": "2026-07-31", "end": "2026-07-01"}

    with pytest.raises(ValidationError, match="start must be on or before end"):
        ProjectCreate.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {**project_payload(), "unexpected": "value"},
        {
            **project_payload(),
            "target": {**project_payload()["target"], "unexpected": "value"},
        },
        {
            **project_payload(),
            "analysis_period": {
                **project_payload()["analysis_period"],
                "unexpected": "value",
            },
        },
    ],
)
def test_project_create_rejects_extra_fields(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ProjectCreate.model_validate(payload)


def test_project_workflow_snapshot_uses_existing_workflow_state() -> None:
    snapshot = ProjectWorkflowSnapshot(
        project_id=uuid4(),
        workflow_state=WorkflowState.CREATED,
    )

    assert snapshot.workflow_state is WorkflowState.CREATED


def test_versioned_run_requires_timezone_aware_created_at() -> None:
    payload = {
        "run_id": str(uuid4()),
        "input_version": "input-v1",
        "output_version": "output-v1",
    }

    with pytest.raises(ValidationError, match="Field required"):
        VersionedRunSchema.model_validate(payload)

    with pytest.raises(ValidationError, match="timezone-aware"):
        VersionedRunSchema.model_validate(
            {**payload, "created_at": "2026-08-14T09:00:00"}
        )

    run = VersionedRunSchema.model_validate(
        {**payload, "created_at": datetime(2026, 8, 14, 9, tzinfo=timezone.utc)}
    )

    assert run.model_dump(mode="json")["created_at"] == "2026-08-14T09:00:00Z"
