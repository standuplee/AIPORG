import asyncio
import json
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.core.enums import ConfidenceGrade, FactStatus, SentimentLabel, StanceLabel
from app.narrative.llm_adapter import GeminiNarrativeAdapter, NarrativeGenerationError
from app.schemas.analytics import AnalyticsSnapshotSchema
from app.schemas.common import VersionedRunSchema
from app.schemas.evidence import EvidenceSchema
from app.schemas.fact import FactSchema
from app.schemas.issue import IssueDetailSchema, IssueSchema
from app.schemas.narrative import NarrativeContext

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


class _FakeResponse:
    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self.body = body

    def json(self):
        return json.loads(self.body)


class _FakeTransport:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.responses = iter(responses)
        self.calls: list[dict[str, object]] = []

    async def post(self, url, *, params=None, json_body=None):
        self.calls.append({"url": url, "params": params, "json_body": json_body})
        return next(self.responses)


def _gemini_payload(sentences: list[dict]) -> str:
    return json.dumps(
        {"candidates": [{"content": {"parts": [{"text": json.dumps(sentences)}]}}]}
    )


def _context_and_inputs():
    fact_id = uuid4()
    document_id = uuid4()
    evidence_id = uuid4()
    project_id = uuid4()
    issue = IssueSchema(
        issue_id=uuid4(),
        label="충남 재정전략회의",
        fact_ids=[fact_id],
        document_count=1,
        source_count=1,
        channel_count=1,
        subissues=[
            IssueDetailSchema(
                label="재정", policy="재정전략회의 개최", summary="회의 개최 확인됨",
                sentiment=SentimentLabel.NEUTRAL, stance=StanceLabel.NOT_APPLICABLE,
            )
        ],
    )
    fact = FactSchema(
        fact_id=fact_id,
        claim="충남도가 재정전략회의를 개최했다.",
        event_date=date(2026, 9, 1),
        entities=["충청남도"],
        evidence_document_ids=[document_id],
        source_count=1,
        confidence=ConfidenceGrade.A,
        status=FactStatus.SUPPORTED,
    )
    context = NarrativeContext(
        issue=issue, facts=[fact], sentiment=SentimentLabel.NEUTRAL,
        keywords=["재정"], positive_reasons=[], negative_reasons=[],
    )
    run = VersionedRunSchema(run_id=uuid4(), input_version="v1", output_version="v1", created_at=NOW)
    analytics = AnalyticsSnapshotSchema(
        project_id=project_id, run=run, metrics={"unique_documents": 3},
    )
    evidence = [
        EvidenceSchema(
            evidence_id=evidence_id, project_id=project_id, document_id=document_id,
            excerpt="충남도가 재정전략회의를 개최했다.", created_at=NOW,
        )
    ]
    return project_id, context, analytics, evidence, fact_id, document_id, evidence_id


def test_generate_keeps_grounded_sentences_and_drops_ungrounded_ones() -> None:
    project_id, context, analytics, evidence, fact_id, document_id, evidence_id = _context_and_inputs()
    body = _gemini_payload(
        [
            {"text": "충남도가 재정전략회의를 개최했다.", "fact_ids": [str(fact_id)]},
            {"text": "주민 90%가 지지했다.", "fact_ids": [str(uuid4())]},  # unknown id, dropped
            {"text": "근거 없는 추정 문장."},  # no reference at all, dropped by schema validation
        ]
    )
    transport = _FakeTransport([_FakeResponse(200, body)])
    adapter = GeminiNarrativeAdapter(api_key="key", transport=transport, now_fn=lambda: NOW)

    output = asyncio.run(
        adapter.generate(
            project_id=project_id, context=context, analytics=analytics, evidence=evidence,
            analytics_run_id=analytics.run.run_id,
        )
    )

    assert len(output.sentences) == 1
    assert output.sentences[0].fact_ids == [fact_id]
    assert output.generation.provider == "gemini"
    assert output.generation.model == "gemini-2.5-flash"
    assert output.analytics_run_id == analytics.run.run_id

    call = transport.calls[0]
    assert call["params"] == {"key": "key"}
    prompt_text = call["json_body"]["contents"][0]["parts"][0]["text"]
    assert str(fact_id) in prompt_text


def test_generate_accepts_evidence_document_and_analytics_grounded_sentences() -> None:
    project_id, context, analytics, evidence, fact_id, document_id, evidence_id = _context_and_inputs()
    body = _gemini_payload(
        [
            {"text": "증거 인용 문장.", "evidence_ids": [str(evidence_id)]},
            {"text": "문서 인용 문장.", "document_ids": [str(document_id)]},
            {"text": "집계 인용 문장.", "analytics_paths": ["unique_documents"]},
        ]
    )
    transport = _FakeTransport([_FakeResponse(200, body)])
    adapter = GeminiNarrativeAdapter(api_key="key", transport=transport, now_fn=lambda: NOW)

    output = asyncio.run(
        adapter.generate(project_id=project_id, context=context, analytics=analytics, evidence=evidence)
    )

    assert len(output.sentences) == 3


def test_generate_raises_when_no_sentence_survives_grounding() -> None:
    project_id, context, analytics, evidence, *_ = _context_and_inputs()
    body = _gemini_payload([{"text": "허위 주장.", "fact_ids": [str(uuid4())]}])
    transport = _FakeTransport([_FakeResponse(200, body)])
    adapter = GeminiNarrativeAdapter(api_key="key", transport=transport, now_fn=lambda: NOW)

    with pytest.raises(NarrativeGenerationError) as raised:
        asyncio.run(
            adapter.generate(project_id=project_id, context=context, analytics=analytics, evidence=evidence)
        )
    assert raised.value.code == "no_grounded_sentences"


def test_generate_raises_on_malformed_gemini_response() -> None:
    project_id, context, analytics, evidence, *_ = _context_and_inputs()
    transport = _FakeTransport([_FakeResponse(200, '{"candidates": []}')])
    adapter = GeminiNarrativeAdapter(api_key="key", transport=transport, now_fn=lambda: NOW)

    with pytest.raises(NarrativeGenerationError) as raised:
        asyncio.run(
            adapter.generate(project_id=project_id, context=context, analytics=analytics, evidence=evidence)
        )
    assert raised.value.code == "malformed_response"


def test_generate_raises_on_http_error_status() -> None:
    project_id, context, analytics, evidence, *_ = _context_and_inputs()
    transport = _FakeTransport([_FakeResponse(503, "")])
    adapter = GeminiNarrativeAdapter(api_key="key", transport=transport, now_fn=lambda: NOW)

    with pytest.raises(NarrativeGenerationError) as raised:
        asyncio.run(
            adapter.generate(project_id=project_id, context=context, analytics=analytics, evidence=evidence)
        )
    assert raised.value.code == "http_status"


def test_constructor_requires_api_key() -> None:
    with pytest.raises(ValueError):
        GeminiNarrativeAdapter(api_key="")
