"""Gemini-backed narrative draft generation.

Per AGENTS.md rules 4/5 (no LLM calls in Collector, no web requests in
Analyzer), LLM calls live only here, never in app/collectors or
app/analytics. Drafting never invents facts: ``NarrativeSentenceSchema``
(app/schemas/narrative.py) already requires every sentence to carry at
least one reference, and this module additionally drops any sentence whose
cited ids/paths are not actually present in the input -- the model's
citations are checked, not trusted.

This only implements the adapter itself (prompt, call, grounding check,
``NarrativeOutputSchema`` assembly). It does not call
``NarrativeRepository.save_output`` and is not wired into
``streamlit_app/console.py`` yet: that requires Issue discovery/finalization
and AnalyticsSnapshot generation to also run in the console first, since a
``NarrativeContext`` needs a real ``IssueSchema`` + ``FactSchema`` list and
there is currently no UI path that produces one (see HANDOFF.md).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from app.schemas.analytics import AnalyticsSnapshotSchema
from app.schemas.common import ProjectId, RunId, VersionedRunSchema
from app.schemas.evidence import EvidenceSchema
from app.schemas.narrative import (
    NarrativeContext,
    NarrativeGenerationSchema,
    NarrativeOutputSchema,
    NarrativeSentenceSchema,
)

GEMINI_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
PROMPT_VERSION = "narrative-v1"


class NarrativeGenerationError(Exception):
    """A narrative draft generation call failed or returned unusable output."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


@dataclass(frozen=True)
class _HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: str

    def json(self) -> Any:
        return json.loads(self.body)


class _Transport(Protocol):
    async def post(
        self,
        url: str,
        *,
        params: Mapping[str, object] | None = None,
        json_body: Mapping[str, object] | None = None,
    ) -> _HttpResponse:
        ...


class _RequestsPostTransport:
    """Minimal async POST transport with bounded retry (mirrors the
    GET-only transport in app/collectors/transport.py, which this module
    deliberately does not import -- narrative draft errors are a different
    domain from collector errors, see NarrativeGenerationError)."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if backoff_seconds < 0:
            raise ValueError("backoff_seconds must be non-negative")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    async def post(
        self,
        url: str,
        *,
        params: Mapping[str, object] | None = None,
        json_body: Mapping[str, object] | None = None,
    ) -> _HttpResponse:
        for attempt in range(self.max_retries + 1):
            try:
                response = await asyncio.to_thread(
                    self._request,
                    url=url,
                    params=dict(params or {}),
                    json_body=dict(json_body or {}),
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:  # noqa: BLE001 - network/library errors, wrap uniformly
                if attempt >= self.max_retries:
                    raise NarrativeGenerationError(
                        code="network_error",
                        message=f"Gemini request failed: {exc}",
                        details={"url": url, "attempts": attempt + 1},
                    ) from exc
                await self._backoff(attempt)
                continue

            if response.status_code not in {429, *range(500, 600)}:
                return response
            if attempt >= self.max_retries:
                raise NarrativeGenerationError(
                    code="http_status",
                    message=f"Gemini request returned status {response.status_code}",
                    details={"status_code": response.status_code, "attempts": attempt + 1},
                )
            await self._backoff(attempt)

        raise AssertionError("retry loop must return or raise")

    async def _backoff(self, attempt: int) -> None:
        delay = self.backoff_seconds * (2**attempt)
        if delay:
            await asyncio.sleep(delay)

    @staticmethod
    def _request(**kwargs: Any) -> _HttpResponse:
        import requests

        kwargs["json"] = kwargs.pop("json_body")
        response = requests.post(**kwargs)
        return _HttpResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.text,
        )


class GeminiNarrativeAdapter:
    """Call Gemini to draft narrative sentences, then verify grounding."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-2.5-flash",
        transport: _Transport | None = None,
        now_fn=None,
    ) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")
        self.api_key = api_key
        self.model = model
        self.transport = transport or _RequestsPostTransport()
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    async def generate(
        self,
        *,
        project_id: ProjectId,
        context: NarrativeContext,
        analytics: AnalyticsSnapshotSchema,
        evidence: Sequence[EvidenceSchema],
        analytics_run_id: RunId | None = None,
        input_version: str = "narrative-context:v1",
    ) -> NarrativeOutputSchema:
        prompt = self._build_prompt(context=context, analytics=analytics, evidence=evidence)
        snapshot_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        raw_sections = await self._call_gemini(prompt)
        sentences = self._ground(
            raw_sections, context=context, analytics=analytics, evidence=evidence
        )

        generated_at = self.now_fn()
        return NarrativeOutputSchema(
            project_id=project_id,
            run=VersionedRunSchema(
                run_id=uuid4(),
                input_version=input_version,
                output_version=f"{PROMPT_VERSION}:{self.model}",
                created_at=generated_at,
            ),
            analytics_run_id=analytics_run_id,
            issue_id=context.issue.issue_id,
            generation=NarrativeGenerationSchema(
                provider="gemini",
                model=self.model,
                prompt_version=PROMPT_VERSION,
                input_snapshot_sha256=snapshot_sha256,
                generated_at=generated_at,
            ),
            sentences=sentences,
        )

    def _build_prompt(
        self,
        *,
        context: NarrativeContext,
        analytics: AnalyticsSnapshotSchema,
        evidence: Sequence[EvidenceSchema],
    ) -> str:
        facts_payload = [
            {
                "fact_id": str(fact.fact_id),
                "claim": fact.claim,
                "status": fact.status.value,
            }
            for fact in context.facts
        ]
        evidence_payload = [
            {
                "evidence_id": str(item.evidence_id),
                "document_id": str(item.document_id),
                "excerpt": item.excerpt,
            }
            for item in evidence
            if item.project_id == analytics.project_id
        ]
        instructions = (
            "다음은 검증된 사실(facts), 근거(evidence), 하위 쟁점(subissues), 집계 수치"
            "(analytics_metrics)다. 이 안에 있는 내용만 사용해 공공기관 보고서 문체의 "
            "한국어 문장을 두 그룹으로 작성하라. 'overview'는 이슈의 발생 배경과 이번 달 "
            "경과를 종합 서술하는 2~4개의 독립된 문장이고, 'closing'은 하위 쟁점별 온라인 "
            "반응을 종합 해석하고 유의사항을 설명하는 1~3개의 독립된 문장이다(하위 쟁점의 "
            "현황표는 별도로 만들어지므로 여기서 표를 반복하지 마라). 응답은 다른 텍스트 "
            "없이 아래 스키마를 따르는 JSON 객체 하나만 반환하라: "
            '{"overview": [{"text": "...", "fact_ids": ["<fact_id>", ...], '
            '"evidence_ids": ["<evidence_id>", ...], "document_ids": ["<document_id>", ...], '
            '"analytics_paths": ["<analytics_metrics의 키>", ...]}, ...], "closing": [...]}. '
            "각 문장은 fact_ids/evidence_ids/document_ids/analytics_paths 중 최소 하나에 "
            "아래에 실제로 주어진 id/키를 정확히 인용해야 하며, 주어진 데이터에 없는 사실·숫자·"
            "고유명사·인과관계를 추가하면 안 된다."
        )
        payload = {
            "issue": {
                "label": context.issue.label,
                "subissues": [
                    {
                        "policy": subissue.policy,
                        "summary": subissue.summary,
                        "sentiment": subissue.sentiment.value,
                    }
                    for subissue in context.issue.subissues
                ],
            },
            "sentiment": context.sentiment.value,
            "keywords": context.keywords,
            "positive_reasons": context.positive_reasons,
            "negative_reasons": context.negative_reasons,
            "facts": facts_payload,
            "evidence": evidence_payload,
            "analytics_metrics": analytics.metrics,
        }
        return instructions + "\n\n" + json.dumps(payload, ensure_ascii=False)

    async def _call_gemini(self, prompt: str) -> dict[str, Any]:
        url = GEMINI_URL_TEMPLATE.format(model=self.model)
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        response = await self.transport.post(url, params={"key": self.api_key}, json_body=body)
        if not 200 <= response.status_code < 300:
            raise NarrativeGenerationError(
                code="http_status",
                message=f"Gemini generateContent returned status {response.status_code}",
                details={"status_code": response.status_code},
            )
        try:
            payload = response.json()
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise NarrativeGenerationError(
                code="malformed_response",
                message=f"Gemini response was not the expected JSON shape: {exc}",
            ) from exc
        if (
            not isinstance(parsed, dict)
            or not isinstance(parsed.get("overview"), list)
            or not isinstance(parsed.get("closing"), list)
        ):
            raise NarrativeGenerationError(
                code="malformed_response",
                message=(
                    "Gemini response JSON must be an object with 'overview' and "
                    "'closing' sentence lists"
                ),
            )
        return parsed

    @staticmethod
    def _ground(
        raw_sections: Mapping[str, Any],
        *,
        context: NarrativeContext,
        analytics: AnalyticsSnapshotSchema,
        evidence: Sequence[EvidenceSchema],
    ) -> list[NarrativeSentenceSchema]:
        allowed_fact_ids = {fact.fact_id for fact in context.facts}
        project_evidence = [item for item in evidence if item.project_id == analytics.project_id]
        allowed_evidence_ids = {item.evidence_id for item in project_evidence}
        allowed_document_ids = {
            doc_id for fact in context.facts for doc_id in fact.evidence_document_ids
        } | {item.document_id for item in project_evidence}
        allowed_analytics_roots = set(analytics.metrics.keys())

        grounded: list[NarrativeSentenceSchema] = []
        for role in ("overview", "closing"):
            for raw in raw_sections.get(role, []):
                try:
                    sentence = NarrativeSentenceSchema.model_validate(
                        {**raw, "role": role} if isinstance(raw, dict) else raw
                    )
                except Exception:  # noqa: BLE001 - malformed candidate, drop it, don't fail the draft
                    continue
                if not set(sentence.fact_ids) <= allowed_fact_ids:
                    continue
                if not set(sentence.evidence_ids) <= allowed_evidence_ids:
                    continue
                if not set(sentence.document_ids) <= allowed_document_ids:
                    continue
                if not all(
                    path.split(".")[0] in allowed_analytics_roots
                    for path in sentence.analytics_paths
                ):
                    continue
                grounded.append(sentence)

        if not grounded:
            raise NarrativeGenerationError(
                code="no_grounded_sentences",
                message=(
                    "Gemini draft contained no sentences grounded in the provided "
                    "facts, evidence, or analytics"
                ),
            )
        return grounded
