# Keyword Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 AIPORG 수집 파이프라인을 공유하면서, 레퍼런스 키워드 조사 보고서 구조를 재현하는 `keyword` 전용 분석 모델, 파이프라인, DOCX 출력 경로를 추가한다.

**Architecture:** 기존 `AnalysisResult -> ReportModel -> narrator -> report writer` 경로는 유지하고, `keyword` 전용으로 `KeywordAnalysisPipeline -> KeywordReportModel -> keyword writer` 경로를 별도 추가한다. CLI는 `report_type` 으로 두 경로를 명시 분기하며, 신규 경로는 비교기간 계산과 설정 기반 `issue_keywords` 를 포함한다.

**Tech Stack:** Python 3, dataclasses, argparse, PyYAML, python-docx, pytest, 기존 AIPORG collect/analyze/report 모듈

---

### Task 1: Extend Config Parsing For Keyword Reports

**Files:**
- Modify: `aiporg/config.py`
- Modify: `config/chungnam_202606.yaml`
- Test: `tests/test_config_keyword_report.py`

- [ ] **Step 1: Write the failing config test**

```python
from aiporg.config import load_config


def test_load_config_parses_keyword_report_settings(tmp_path):
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text(
        """
project_name: 충청남도
subject:
  name: 충청남도
  leader_title: 도지사
  leader_name: 박수현
period:
  start: 2026.07.01
  end: 2026.07.31
report_title: 2026년 7월 충청남도 온라인 여론 분석
keywords:
  충청남도: [충남, 박수현]
keyword_report:
  issue_keywords:
    AI수도 충남: [AI수도 충남, 충남 AI]
""",
        encoding="utf-8",
    )

    cfg = load_config(str(cfg_file))

    assert cfg.keyword_report.issue_keywords["AI수도 충남"] == ["AI수도 충남", "충남 AI"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_keyword_report.py -v`
Expected: FAIL because `RunConfig` has no `keyword_report` field.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class KeywordReportConfig:
    issue_keywords: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class RunConfig:
    ...
    keyword_report: KeywordReportConfig = field(default_factory=KeywordReportConfig)
```

Implement YAML parsing so `raw.get("keyword_report", {})` maps into `KeywordReportConfig`.

- [ ] **Step 4: Update the sample config**

Add `keyword_report.issue_keywords` to `config/chungnam_202606.yaml` with the approved short-form issue keyword groups from the spec.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_config_keyword_report.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add aiporg/config.py config/chungnam_202606.yaml tests/test_config_keyword_report.py
git commit -m "feat: parse keyword report config"
```

### Task 2: Add Keyword Report Data Models

**Files:**
- Create: `aiporg/models_keyword_report.py`
- Test: `tests/test_models_keyword_report.py`

- [ ] **Step 1: Write the failing model round-trip test**

```python
from aiporg.models_keyword_report import KeywordReportModel, KeywordReportSummary


def test_keyword_report_model_to_dict_roundtrip():
    model = KeywordReportModel(
        summary=KeywordReportSummary(
            analysis_period="2026.07.01~2026.07.31",
            channel_count=6,
            primary_keyword="박수현",
            positive_ratio=58.0,
            month_over_month="▼3%p",
        )
    )

    raw = model.to_dict()
    restored = KeywordReportModel.from_dict(raw)

    assert restored.summary.primary_keyword == "박수현"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models_keyword_report.py -v`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Write minimal implementation**

Create focused dataclasses for:

```python
KeywordReportSummary
KeywordIssue
ChannelTrendItem
RankedKeywordItem
SentimentDriver
SourceReference
KeywordReportModel
```

Include `to_dict`/`from_dict` helpers for deterministic tests and future JSON fixture support.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models_keyword_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add aiporg/models_keyword_report.py tests/test_models_keyword_report.py
git commit -m "feat: add keyword report models"
```

### Task 3: Build Comparison-Period Helper

**Files:**
- Create: `aiporg/analyze_keyword_report/periods.py`
- Test: `tests/test_keyword_report_periods.py`

- [ ] **Step 1: Write the failing comparison-period test**

```python
from datetime import date

from aiporg.analyze_keyword_report.periods import previous_month_range


def test_previous_month_range_for_july():
    start, end = previous_month_range(date(2026, 7, 1), date(2026, 7, 31))
    assert start.isoformat() == "2026-06-01"
    assert end.isoformat() == "2026-06-30"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyword_report_periods.py -v`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def previous_month_range(start: date, end: date) -> tuple[date, date]:
    ...
```

Handle month/year boundaries explicitly and keep the function deterministic.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keyword_report_periods.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add aiporg/analyze_keyword_report/periods.py tests/test_keyword_report_periods.py
git commit -m "feat: add keyword report comparison period helper"
```

### Task 4: Add Keyword Classification Dictionaries

**Files:**
- Create: `aiporg/analyze_keyword_report/dictionaries.py`
- Test: `tests/test_keyword_report_dictionaries.py`

- [ ] **Step 1: Write the failing dictionary test**

```python
from aiporg.analyze_keyword_report.dictionaries import categorize_keyword


def test_categorize_keyword_maps_known_terms():
    assert categorize_keyword("청년AI인재") == "교육/고용"
    assert categorize_keyword("민생지원금") == "민생/복지"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyword_report_dictionaries.py -v`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Write minimal implementation**

Create explicit dictionaries and helpers:

```python
KEYWORD_CATEGORY_RULES = {...}
STOPWORDS = {...}

def categorize_keyword(term: str) -> str:
    ...
```

Keep rules code-owned, not model-generated.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keyword_report_dictionaries.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add aiporg/analyze_keyword_report/dictionaries.py tests/test_keyword_report_dictionaries.py
git commit -m "feat: add keyword report dictionaries"
```

### Task 5: Implement Keyword Ranking And Category Mapping

**Files:**
- Create: `aiporg/analyze_keyword_report/keywords.py`
- Test: `tests/test_keyword_report_keywords.py`

- [ ] **Step 1: Write the failing keyword ranking test**

```python
from aiporg.models import Channel, Document
from aiporg.analyze_keyword_report.keywords import top_ranked_keywords


def test_top_ranked_keywords_returns_ranked_categorized_items():
    docs = [
        Document(doc_id="1", channel=Channel.NEWS, title="청년AI인재 양성", body="충남 AI 인재", url="u1"),
        Document(doc_id="2", channel=Channel.X, title="민생지원금 확대", body="민생지원금", url="u2"),
    ]
    items = top_ranked_keywords(docs, top_n=5)
    assert items[0].rank == 1
    assert items[0].category
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyword_report_keywords.py -v`
Expected: FAIL because helper does not exist.

- [ ] **Step 3: Write minimal implementation**

Use existing text helpers where possible, then convert ranked terms into `RankedKeywordItem` with deterministic tie-breakers:
- higher frequency first
- wider channel coverage second
- lexical order third

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keyword_report_keywords.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add aiporg/analyze_keyword_report/keywords.py tests/test_keyword_report_keywords.py
git commit -m "feat: rank keyword report keywords"
```

### Task 6: Implement Issue Selection With Issue Keyword Weighting

**Files:**
- Create: `aiporg/analyze_keyword_report/issues.py`
- Test: `tests/test_keyword_report_issues.py`

- [ ] **Step 1: Write the failing issue ranking test**

```python
from aiporg.models import Channel, Document
from aiporg.analyze_keyword_report.issues import rank_issues


def test_rank_issues_prefers_cluster_with_issue_keyword_hits():
    docs = [
        Document(doc_id="1", channel=Channel.NEWS, title="AI수도 충남 추진", body="충남 AI 3력 혁신", url="u1"),
        Document(doc_id="2", channel=Channel.X, title="AI수도 충남", body="AI수도 충남", url="u2"),
        Document(doc_id="3", channel=Channel.NEWS, title="기타 이슈", body="일반 내용", url="u3"),
    ]
    issues = rank_issues(docs, issue_keywords={"AI수도 충남": ["AI수도 충남", "충남 AI"]}, top_n=4)
    assert issues[0].title
    assert "AI" in issues[0].title or "AI" in issues[0].body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyword_report_issues.py -v`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Write minimal implementation**

Implement:
- simple cluster grouping
- issue keyword hit counting
- comparison-period growth scoring hook
- deterministic tie-breakers from the spec

Return `KeywordIssue` items with `representative_documents`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keyword_report_issues.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add aiporg/analyze_keyword_report/issues.py tests/test_keyword_report_issues.py
git commit -m "feat: add keyword report issue ranking"
```

### Task 7: Implement Channel Trend Analysis

**Files:**
- Create: `aiporg/analyze_keyword_report/channels.py`
- Test: `tests/test_keyword_report_channels.py`

- [ ] **Step 1: Write the failing channel trend test**

```python
from aiporg.models import Channel, Document
from aiporg.analyze_keyword_report.channels import build_channel_trends


def test_build_channel_trends_returns_change_direction():
    current_docs = [Document(doc_id="1", channel=Channel.X, title="폭염", body="기후재난", url="u1")]
    previous_docs = []
    items = build_channel_trends(current_docs, previous_docs)
    assert items[0].change_direction in {"▲ 증가", "▼ 감소", "— 유지", "비교 불가"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyword_report_channels.py -v`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Write minimal implementation**

Compute:
- channel volume/share
- prior-month comparison
- fallback `비교 불가`
- per-channel representative keywords

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keyword_report_channels.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add aiporg/analyze_keyword_report/channels.py tests/test_keyword_report_channels.py
git commit -m "feat: add keyword report channel trends"
```

### Task 8: Implement Sentiment Driver Extraction

**Files:**
- Create: `aiporg/analyze_keyword_report/sentiment.py`
- Test: `tests/test_keyword_report_sentiment.py`

- [ ] **Step 1: Write the failing sentiment-driver test**

```python
from aiporg.models import Channel, Document, Sentiment
from aiporg.analyze_keyword_report.sentiment import build_sentiment_drivers


def test_build_sentiment_drivers_extracts_positive_and_negative_groups():
    docs = [
        Document(doc_id="1", channel=Channel.NEWS, title="AI수도 충남 기대", body="일자리 기대", url="u1", sentiment=Sentiment.POSITIVE),
        Document(doc_id="2", channel=Channel.X, title="폭염 대응 비판", body="취약계층 대책 부족", url="u2", sentiment=Sentiment.NEGATIVE),
    ]
    pos, neg = build_sentiment_drivers(docs)
    assert pos
    assert neg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyword_report_sentiment.py -v`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Write minimal implementation**

Build deterministic positive/negative driver lists using existing sentiment labels plus keyword extraction and representative evidence selection.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keyword_report_sentiment.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add aiporg/analyze_keyword_report/sentiment.py tests/test_keyword_report_sentiment.py
git commit -m "feat: add keyword report sentiment drivers"
```

### Task 9: Implement Source Reference Builder

**Files:**
- Create: `aiporg/analyze_keyword_report/sources.py`
- Test: `tests/test_keyword_report_sources.py`

- [ ] **Step 1: Write the failing source-reference test**

```python
from aiporg.models import Channel, Document
from aiporg.analyze_keyword_report.sources import build_source_references


def test_build_source_references_deduplicates_urls():
    docs = [
        Document(doc_id="1", channel=Channel.NEWS, title="t1", body="b", url="https://x/1"),
        Document(doc_id="2", channel=Channel.NEWS, title="t1 copy", body="b", url="https://x/1"),
    ]
    refs = build_source_references(docs)
    assert len(refs) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyword_report_sources.py -v`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Write minimal implementation**

Deduplicate by URL, preserve readable source metadata, and sort for stable output.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keyword_report_sources.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add aiporg/analyze_keyword_report/sources.py tests/test_keyword_report_sources.py
git commit -m "feat: add keyword report source references"
```

### Task 10: Implement Recommendations And Methodology Builders

**Files:**
- Create: `aiporg/analyze_keyword_report/recommendations.py`
- Create: `aiporg/analyze_keyword_report/methodology.py`
- Test: `tests/test_keyword_report_recommendations.py`

- [ ] **Step 1: Write the failing recommendations test**

```python
from aiporg.models_keyword_report import KeywordIssue, SentimentDriver
from aiporg.analyze_keyword_report.recommendations import build_recommendations


def test_build_recommendations_returns_implications_and_channel_actions():
    issues = [KeywordIssue(rank=1, title="폭염 기후재난", subtitle="", body="폭염 대응 이슈", evidence=[], source_notes=[])]
    negative = [SentimentDriver(sentiment="부정", title="폭염 대응 비판", detail="취약계층 대책 부족", evidence=[])]
    implications, channel_actions = build_recommendations(issues, [], negative)
    assert implications
    assert channel_actions
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyword_report_recommendations.py -v`
Expected: FAIL because builders do not exist.

- [ ] **Step 3: Write minimal implementation**

Add deterministic builders for:
- `implications`
- `channel_recommendations`
- `methodology` summary text

These builders must be evidence-aware and must not depend on optional LLM behavior.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keyword_report_recommendations.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add aiporg/analyze_keyword_report/recommendations.py aiporg/analyze_keyword_report/methodology.py tests/test_keyword_report_recommendations.py
git commit -m "feat: add keyword report recommendations"
```

### Task 11: Build The Keyword Report Pipeline In Small Steps

**Files:**
- Create: `aiporg/analyze_keyword_report/__init__.py`
- Create: `aiporg/analyze_keyword_report/pipeline.py`
- Test: `tests/test_keyword_report_pipeline.py`

- [ ] **Step 1: Write the failing pipeline integration test**

```python
from datetime import date

from aiporg.analyze_keyword_report.pipeline import KeywordAnalysisPipeline
from aiporg.models import Channel, Document, ReportMeta


def test_keyword_pipeline_builds_keyword_report_model():
    meta = ReportMeta(
        project_name="충청남도",
        subject_name="충청남도",
        leader_title="도지사",
        leader_name="박수현",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        keywords={"충청남도": ["충남", "박수현"]},
        report_title="test",
    )
    docs = [Document(doc_id="1", channel=Channel.NEWS, title="AI수도 충남", body="충남 AI", url="u1")]
    model = KeywordAnalysisPipeline().run(docs, [], meta, issue_keywords={"AI수도 충남": ["AI수도 충남"]})
    assert model.issues
    assert model.summary.primary_keyword == "박수현"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyword_report_pipeline.py -v`
Expected: FAIL because pipeline does not exist.

- [ ] **Step 3: Write minimal pipeline shell**

Implement the class and method signature first:

```python
class KeywordAnalysisPipeline:
    def run(self, current_docs, previous_docs, meta, issue_keywords=None):
        ...
```

- [ ] **Step 4: Add summary and comparison fallback behavior**

Implement explicit handling for:
- current-period summary fields
- comparison-period month-over-month calculation
- `비교 불가` fallback when `previous_docs` is empty

- [ ] **Step 5: Add evidence-backed assembly**

Integrate:
- issues
- channels
- keywords
- sentiment
- sources
- implications
- methodology

Ensure every narrative section maps back to previously built evidence-bearing components.

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_keyword_report_pipeline.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add aiporg/analyze_keyword_report/__init__.py aiporg/analyze_keyword_report/pipeline.py tests/test_keyword_report_pipeline.py
git commit -m "feat: add keyword report pipeline"
```

### Task 12: Add Keyword Report DOCX Layout Helpers

**Files:**
- Create: `aiporg/report/keyword_layout.py`
- Create: `aiporg/report/keyword_sections.py`
- Test: `tests/test_keyword_report_layout.py`

- [ ] **Step 1: Write the failing layout helper test**

```python
from aiporg.report.keyword_layout import summary_labels


def test_summary_labels_contains_required_fields():
    labels = summary_labels()
    assert "분석기간" in labels
    assert "핵심 검색어" in labels
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyword_report_layout.py -v`
Expected: FAIL because helpers do not exist.

- [ ] **Step 3: Write minimal implementation**

Extract reusable layout decisions for:
- static TOC items
- summary card labels
- section labels
- empty-state phrases

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keyword_report_layout.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add aiporg/report/keyword_layout.py aiporg/report/keyword_sections.py tests/test_keyword_report_layout.py
git commit -m "feat: add keyword report layout helpers"
```

### Task 13: Add Keyword Report Chart Rendering Contract

**Files:**
- Create: `aiporg/charts/keyword_render.py`
- Test: `tests/test_keyword_report_charts.py`

- [ ] **Step 1: Write the failing chart rendering test**

```python
from aiporg.charts.keyword_render import KeywordChartRenderer
from aiporg.models_keyword_report import KeywordReportModel


def test_keyword_chart_renderer_returns_mapping(tmp_path):
    renderer = KeywordChartRenderer(str(tmp_path))
    charts = renderer.render_all(KeywordReportModel())
    assert isinstance(charts, dict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyword_report_charts.py -v`
Expected: FAIL because renderer does not exist.

- [ ] **Step 3: Write minimal implementation**

Add only charts needed for the keyword report structure. Define the fallback contract explicitly:
- renderer returns a stable dict of optional chart paths
- missing charts are legal
- section fallback ownership lives in `keyword_sections.py`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keyword_report_charts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add aiporg/charts/keyword_render.py tests/test_keyword_report_charts.py
git commit -m "feat: add keyword report charts"
```

### Task 14: Implement Keyword Report DOCX Writer

**Files:**
- Create: `aiporg/report/keyword_docx_writer.py`
- Modify: `aiporg/report/__init__.py`
- Test: `tests/test_keyword_report_docx_writer.py`

- [ ] **Step 1: Write the failing DOCX writer structure test**

```python
from docx import Document as Docx

from aiporg.models_keyword_report import KeywordReportModel, KeywordReportSummary
from aiporg.report.keyword_docx_writer import write_keyword_docx


def test_write_keyword_docx_contains_required_headings(tmp_path):
    out = tmp_path / "keyword.docx"
    model = KeywordReportModel(
        summary=KeywordReportSummary(
            analysis_period="2026.07.01~2026.07.31",
            channel_count=6,
            primary_keyword="박수현",
            positive_ratio=58.0,
            month_over_month="▼3%p",
        )
    )

    write_keyword_docx(model, str(out), charts={})

    doc = Docx(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "CONTENTS" in text
    assert "REPORT SUMMARY" in text
    assert "제1장" in text
    assert "제6장" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyword_report_docx_writer.py -v`
Expected: FAIL because writer does not exist.

- [ ] **Step 3: Write minimal implementation**

Implement a dedicated writer with:
- cover
- static TOC
- summary page
- chapter 1-6 headings
- chart-or-table fallback hooks delegated through `keyword_sections.py`
- empty-state-safe sections

Do not route through the existing narrator-based writer.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keyword_report_docx_writer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add aiporg/report/keyword_docx_writer.py aiporg/report/__init__.py tests/test_keyword_report_docx_writer.py
git commit -m "feat: add keyword report docx writer"
```

### Task 15: Wire Comparison-Period Collection Into Real Run Flow

**Files:**
- Modify: `aiporg/cli.py`
- Optionally Modify: `aiporg/collect/base.py`
- Test: `tests/test_cli_keyword_report_collection.py`

- [ ] **Step 1: Write the failing collection wiring test**

```python
from datetime import date

from aiporg.analyze_keyword_report.periods import previous_month_range


def test_keyword_report_run_uses_previous_month_range():
    start, end = previous_month_range(date(2026, 7, 1), date(2026, 7, 31))
    assert (start.isoformat(), end.isoformat()) == ("2026-06-01", "2026-06-30")
```

Add a CLI-level integration test that asserts the keyword flow attempts to build both current and previous `Document` sets from the same collectors.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_keyword_report_collection.py -v`
Expected: FAIL because CLI does not yet build comparison documents.

- [ ] **Step 3: Write minimal implementation**

In the real `run` flow:
- build current-period docs with existing collector rules
- build previous-period docs with the same collector names and max-doc limits
- pass both sets into `KeywordAnalysisPipeline`

Do not leave previous docs as a test-only empty list.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_keyword_report_collection.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add aiporg/cli.py aiporg/collect/base.py tests/test_cli_keyword_report_collection.py
git commit -m "feat: collect comparison period for keyword report"
```

### Task 16: Integrate CLI Dispatch And Format Validation

**Files:**
- Modify: `aiporg/cli.py`
- Modify: `aiporg/config.py`
- Test: `tests/test_cli_keyword_report.py`

- [ ] **Step 1: Write the failing CLI test**

```python
import pytest

from aiporg.cli import main


def test_keyword_report_rejects_non_docx_format():
    with pytest.raises(SystemExit):
        main([
            "run",
            "--config", "config/chungnam_202606.yaml",
            "--report-type", "keyword",
            "--formats", "docx,html",
        ])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_keyword_report.py -v`
Expected: FAIL because CLI has no keyword report validation.

- [ ] **Step 3: Write minimal implementation**

Add:
- `--report-type` argument
- default `docx` when `report_type=keyword` and formats omitted
- explicit validation failure for non-`docx`
- pipeline/writer dispatch into the new keyword report path

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_keyword_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add aiporg/cli.py aiporg/config.py tests/test_cli_keyword_report.py
git commit -m "feat: wire keyword report cli flow"
```

### Task 17: Add Existing-Flow Regression Coverage

**Files:**
- Create: `tests/test_cli_default_report.py`
- Modify: `tests/test_cli_keyword_report.py`

- [ ] **Step 1: Write the failing default-flow regression test**

```python
from aiporg.cli import main


def test_default_report_type_still_accepts_existing_formats(tmp_path):
    out_dir = tmp_path / "out"
    main([
        "run",
        "--config", "config/chungnam_202606.yaml",
        "--formats", "json",
        "--out", str(out_dir),
    ])
    assert list(out_dir.glob("*_analysis.json"))
```

- [ ] **Step 2: Run test to verify it fails or exposes regressions**

Run: `pytest tests/test_cli_default_report.py -v`
Expected: PASS only after the new CLI branching preserves default behavior.

- [ ] **Step 3: Write or adjust implementation**

Protect:
- default `run` dispatch
- existing format handling
- non-keyword writer path

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_default_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli_default_report.py tests/test_cli_keyword_report.py aiporg/cli.py
git commit -m "test: protect existing report cli flow"
```

### Task 18: Add End-to-End Fixture Coverage For Keyword Report

**Files:**
- Create: `tests/test_keyword_report_e2e.py`
- Optionally Create: `aiporg/data/keyword_report_fixture.json`

- [ ] **Step 1: Write the failing end-to-end test**

```python
from pathlib import Path

from aiporg.cli import main


def test_keyword_report_e2e_generates_docx(tmp_path):
    out_dir = tmp_path / "out"
    main([
        "run",
        "--config", "config/chungnam_202606.yaml",
        "--report-type", "keyword",
        "--formats", "docx",
        "--out", str(out_dir),
    ])
    files = list(out_dir.glob("*.docx"))
    assert files
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyword_report_e2e.py -v`
Expected: FAIL until keyword flow is fully wired.

- [ ] **Step 3: Write minimal implementation or fixture support**

If live collection makes tests unstable, add a deterministic fixture path for keyword report tests and route the integration through stable local data.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keyword_report_e2e.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_keyword_report_e2e.py aiporg/data/keyword_report_fixture.json
git commit -m "test: cover keyword report end to end"
```

### Task 19: Strengthen DOCX Structure Verification

**Files:**
- Modify: `tests/test_keyword_report_docx_writer.py`
- Optionally Create: `tests/fixtures/keyword_report_expected_sections.txt`

- [ ] **Step 1: Add failing structure assertions**

Extend the writer test to verify:
- exact section order
- TOC presence
- summary labels
- chapter 1-6 presence
- fallback text when chart mapping is empty

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyword_report_docx_writer.py -v`
Expected: FAIL until stronger assertions are satisfied.

- [ ] **Step 3: Adjust writer or fixture expectations**

Keep the verification deterministic by using extracted paragraph text or document XML rather than manual inspection only.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keyword_report_docx_writer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_keyword_report_docx_writer.py tests/fixtures/keyword_report_expected_sections.txt aiporg/report/keyword_docx_writer.py
git commit -m "test: strengthen keyword report docx verification"
```

### Task 20: Run Full Regression Verification

**Files:**
- Modify as needed: any files touched during verification fixes

- [ ] **Step 1: Run focused keyword report suite**

Run:

```bash
pytest tests/test_config_keyword_report.py \
  tests/test_models_keyword_report.py \
  tests/test_keyword_report_periods.py \
  tests/test_keyword_report_dictionaries.py \
  tests/test_keyword_report_keywords.py \
  tests/test_keyword_report_issues.py \
  tests/test_keyword_report_channels.py \
  tests/test_keyword_report_sentiment.py \
  tests/test_keyword_report_sources.py \
  tests/test_keyword_report_recommendations.py \
  tests/test_keyword_report_pipeline.py \
  tests/test_keyword_report_layout.py \
  tests/test_keyword_report_docx_writer.py \
  tests/test_keyword_report_charts.py \
  tests/test_cli_keyword_report_collection.py \
  tests/test_cli_keyword_report.py \
  tests/test_cli_default_report.py \
  tests/test_keyword_report_e2e.py -v
```

Expected: PASS

- [ ] **Step 2: Run existing regression suite**

Run:

```bash
pytest tests/test_cli_default_report.py -v
pytest tests/test_youtube.py -v
```

Expected: PASS

- [ ] **Step 3: Run representative existing sample generation**

Run:

```bash
python -m aiporg.cli run \
  --config config/chungnam_202606.yaml \
  --formats json \
  --out output_regression
```

Expected: Existing report flow still generates its normal artifact set for the requested formats.

- [ ] **Step 4: Run representative keyword sample generation**

Run:

```bash
pytest tests/test_youtube.py -v
python -m aiporg.cli run \
  --config config/chungnam_202606.yaml \
  --report-type keyword \
  --formats docx \
  --out output_keyword
```

Expected: DOCX file generated successfully.

- [ ] **Step 5: Review output structure manually**

Check:
- cover
- CONTENTS
- REPORT SUMMARY
- chapter 1-6 order
- empty-state handling if data is missing
- table/chart fallback behavior
- source/methodology sections present

- [ ] **Step 6: Commit final verification fixes**

```bash
git add <touched-files>
git commit -m "test: verify keyword report flow"
```
