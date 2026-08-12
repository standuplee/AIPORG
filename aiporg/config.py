"""입력 설정 로더/검증.

사용자는 PRD 4항의 최소 입력값만 제공한다:
  프로젝트명 / 분석기간 / 키워드(수집 체계) / 보고서 제목 / 분석 대상.
YAML 설정을 읽어 ReportMeta 및 실행 옵션(RunConfig)으로 변환한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import yaml

from .models import ReportMeta


@dataclass
class KeywordReportConfig:
    issue_keywords: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class RunConfig:
    meta: ReportMeta
    # 실행 옵션
    collectors: list[str] = field(default_factory=list)   # 활성 수집기
    llm_provider: str = "template"                          # template|gemini|openai
    llm_model: str = ""
    data_fixture: str | None = None    # 사전 산출된 분석 데이터(json) 경로
    max_docs_per_collector: int = 200
    seed: int = 42                     # 재현성 보장용 시드
    keyword_report: KeywordReportConfig = field(default_factory=KeywordReportConfig)

    raw: dict[str, Any] = field(default_factory=dict)


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).replace(".", "-").strip())


def load_config(path: str) -> RunConfig:
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    _validate(raw)

    period = raw["period"]
    meta = ReportMeta(
        project_name=raw["project_name"],
        subject_name=raw["subject"]["name"],
        leader_title=raw["subject"].get("leader_title", "도지사"),
        leader_name=raw["subject"]["leader_name"],
        period_start=_parse_date(period["start"]),
        period_end=_parse_date(period["end"]),
        keywords=raw["keywords"],
        report_title=raw["report_title"],
        tool_name=raw.get("tool_name", "Lucy 2.0(RSN)"),
    )

    llm = raw.get("llm", {})
    keyword_report_raw = raw.get("keyword_report", {})
    return RunConfig(
        meta=meta,
        collectors=raw.get("collectors", []),
        llm_provider=llm.get("provider", "template"),
        llm_model=llm.get("model", ""),
        data_fixture=raw.get("data_fixture"),
        max_docs_per_collector=raw.get("max_docs_per_collector", 200),
        seed=raw.get("seed", 42),
        keyword_report=KeywordReportConfig(
            issue_keywords=keyword_report_raw.get("issue_keywords", {}),
        ),
        raw=raw,
    )


REQUIRED = ["project_name", "subject", "period", "keywords", "report_title"]


def _validate(raw: dict) -> None:
    missing = [k for k in REQUIRED if k not in raw]
    if missing:
        raise ValueError(f"설정 누락 항목: {', '.join(missing)}")
    if "name" not in raw["subject"] or "leader_name" not in raw["subject"]:
        raise ValueError("subject.name 과 subject.leader_name 은 필수입니다")
    if "start" not in raw["period"] or "end" not in raw["period"]:
        raise ValueError("period.start / period.end 는 필수입니다")
    if not isinstance(raw["keywords"], dict) or not raw["keywords"]:
        raise ValueError("keywords 는 '구분 -> 키워드목록' 형태의 매핑이어야 합니다")
