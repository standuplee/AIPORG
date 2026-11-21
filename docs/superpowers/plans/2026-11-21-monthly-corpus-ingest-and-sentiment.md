# 월간 종합 1단계: 코퍼스 적재 · 문서 감성 분류 · 분류 검수 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 새 엔진이 모은 이슈별 문서를 2.0 DB로 적재하고, 문서별 감성을 Qwen으로 분류·표본 검수해 2.0 Analytics가 감성 분포를 계산할 수 있게 한다.

**Architecture:** 새 엔진 결과를 `IssueCorpus` JSON으로 저장 → `BaseCollector` 규격의 `ReplayCollector`가 이를 돌려주어 기존 `MultiQueryCollectionToEvidenceWorkflow`를 그대로 탄다. 감성은 분석 계층에서 Qwen이 라벨·근거를 내고 코드가 근거를 확인한 뒤 기존 `upsert_clean`으로 `metadata["sentiment"]`에 병합 저장한다(Analytics는 이 키를 이미 센다). 검수는 Streamlit 페이지에서 표본을 확인한다.

**Tech Stack:** Python 3.12, Pydantic, SQLAlchemy/SQLite(기존 Repository), Streamlit(AppTest), 로컬 Ollama qwen3:8b(`QwenQueryExpansionService.chat`), pytest.

**Spec:** [월간 종합 설계](../specs/2026-11-21-monthly-synthesis-design.md) (프로젝트 1~3). 프로젝트 4(지표·장 조립)와 5(시각 자료·HWPX)는 이 계획의 결과를 확인한 뒤 별도 계획으로 쓴다.

## Global Constraints

- 새 schema 임의 추가 금지: 이 계획이 추가하는 모델은 `CorpusItem`, `IssueCorpus`, `SentimentVerdict`(설계 §5.2에 명시)뿐이다. 기존 Pydantic 모델 이름 변경 금지. DB 테이블·컬럼·enum 값 추가 금지.
- DB write는 Repository(`SqlAlchemyDocumentRepository` 등)로만. Collector(`ReplayCollector`)에서 LLM 호출 금지. 감성 분류(분석 계층)에서 웹 요청 금지.
- 모든 숫자(건수·보류·표본)는 데이터에서 계산한다. 모듈 변경마다 단위 테스트, 통합 테스트가 실패하면 다음 Task로 넘어가지 않는다.
- 2.0 `RawDocument.published_at`은 필수: 게시일 없는 글은 적재하지 않고 "보류"로 기록한다. 채널은 `ChannelType`(news/blog/community/social/video)만 쓴다: NEWS→news, BLOG→blog, CAFE→community, WEB→출처 유형이 NEWS일 때만 news, 그 외는 보류(`unmapped_channel`).
- `DocumentRepository.upsert_clean`은 `source_metadata`를 **덮어쓴다**(병합하지 않음). 메타데이터를 갱신할 때는 `get()`으로 읽은 기존 `metadata`에 병합해서 넘긴다.
- 감성 값은 `metadata["sentiment"] ∈ {"positive","negative","neutral","mixed"}`일 때만 집계된다. 분류 못 한 문서는 이 키를 쓰지 않는다(→ `unclassified`).
- 로컬 Qwen은 실행마다 결과가 달라진다: 분류 결과는 메타데이터에 저장하고 이후 단계는 저장값만 쓴다.
- 커밋 메시지 형식 `<type>(scope): <subject>`, 도구 이름·`Co-authored-by` 문구 금지(저장소 규칙).

## Review Focus

1. 게시일이 전부 없는 이슈: 적재 0건이어도 예외 없이 끝나고 보류 건수가 요약에 나온다 (Task 3).
2. 같은 URL이 사실·반응 양쪽 검색에 나온 경우: 코퍼스에 한 건, 2.0에서도 한 문서 (Task 1, 3).
3. Qwen 근거 구절이 공백·줄바꿈만 다르거나 아예 원문에 없는 경우: 앞은 인정, 뒤는 미분류 (Task 4).
4. 분류를 다시 돌릴 때: 기존 메타데이터(`body_available` 등)와 사람이 검수한 문서의 라벨은 유지된다 (Task 5).
5. 이슈 문서가 표본 크기보다 적거나 Qwen이 응답하지 않는 경우: 표본은 전체, 응답 없는 문서는 미분류로 남고 건수가 집계된다 (Task 4, 6).

---

## File Structure

| 파일 | 책임 |
|---|---|
| `app/research/corpus.py` (신규) | `CorpusItem`, `IssueCorpus`, `build_corpus`, `save_corpus`, `load_corpus` |
| `app/collectors/replay.py` (신규) | 채널 매핑·보류 분류(`partition`), `ReplayCollector` |
| `app/workflows/ingest_issue_corpora.py` (신규) | 프로젝트 질의 준비 + 수집 워크플로 실행, 적재 요약 |
| `app/sentiment/document_classifier.py` (신규) | Qwen 문서 감성 분류, 근거 확인, 저장, 프로젝트 단위 실행 |
| `app/sentiment/review.py` (신규) | 검수 표본 선택, 검수 기록, 검수 요약 |
| `streamlit_app/sentiment_review.py` (신규), `streamlit_app/console.py` (수정) | 검수 화면과 메뉴 연결 |
| `tests_v2/unit/test_corpus.py`, `test_replay_collector.py`, `test_document_sentiment.py`, `test_sentiment_review.py`, `tests_v2/integration/test_monthly_ingest_sentiment.py` | 각 Task의 테스트 |

---

### Task 1: IssueCorpus 저장 형식

**Files:**
- Create: `app/research/corpus.py`
- Test: `tests_v2/unit/test_corpus.py`

**Interfaces:**
- Produces:
  - `class CorpusItem(SchemaBase)`: `result_id: str`, `channel: str` ("NEWS"|"BLOG"|"CAFE"|"WEB"), `title: str`, `url: str`, `snippet: str`, `published_at: AwareDatetime | None = None`, `kind: Literal["FACT","OPINION"]`, `source_type: str`, `body: str | None = None`.
  - `class IssueCorpus(SchemaBase)`: `issue: str`, `region: str`, `start_date: date`, `end_date: date`, `items: list[CorpusItem]`.
  - `build_corpus(issue: IssueInput, fact_hits: list[app.search.schemas.SearchResult], fetched: dict[str, FetchedDocument], opinion_posts: list[DiscussionPost]) -> IssueCorpus`
  - `save_corpus(path: Path, corpus: IssueCorpus) -> None`, `load_corpus(path: Path) -> IssueCorpus`

- [ ] **Step 1: Write the failing tests** in `test_corpus.py`:
  - `test_build_corpus_merges_fact_and_opinion_and_keeps_one_item_per_result_id`: 사실 검색 결과 2건(하나는 `fetched`에 본문 있음) + 반응 글 2건(하나는 사실 쪽과 같은 `result_id`) → `len(items) == 3`, 중복 항목의 `kind == "FACT"`, 본문 있는 항목의 `body == fetched[id].text`, 본문 없는 항목의 `body is None`.
  - `test_source_type_comes_from_fetched_document_then_registry_then_channel`: fetched 있으면 그 `source_type.value`, 없으면 `app.search.signals.source_type(result).value`, 반응 글은 BLOG→"BLOG", CAFE→"COMMUNITY".
  - `test_save_and_load_round_trip_keeps_missing_published_at_as_none`.
- [ ] **Step 2: Run** `./.venv/bin/python -m pytest tests_v2/unit/test_corpus.py -q` → FAIL (module missing).
- [ ] **Step 3: Implement** `app/research/corpus.py`. 사실 항목은 `SearchResult`의 `original_url or url`을 `url`로, `channel.value`를 `channel`로 쓴다. `result_id`로 중복 제거(먼저 들어온 FACT가 우선). 저장은 `model_dump_json(indent=2)`, UTF-8.
- [ ] **Step 4: Run** the test file → PASS.
- [ ] **Step 5: Commit** `feat(research): add issue corpus store for monthly ingestion`

---

### Task 2: ReplayCollector

**Files:**
- Create: `app/collectors/replay.py`
- Test: `tests_v2/unit/test_replay_collector.py`

**Interfaces:**
- Consumes: `IssueCorpus`, `CorpusItem` (Task 1); `app.collectors.base.BaseCollector`; 2.0 `SearchResult`, `RawDocument` (`app/schemas/document.py`), `SearchQuery`, `ChannelType`.
- Produces:
  - `map_channel(item: CorpusItem) -> ChannelType | None` (Global Constraints의 매핑)
  - `partition(corpus: IssueCorpus) -> tuple[list[tuple[CorpusItem, ChannelType]], dict[str, str]]` — 적재 가능 항목과 보류 `{result_id: "undated" | "unmapped_channel"}`. 게시일이 없으면 `undated`가 채널 매핑 실패보다 우선한다.
  - `class ReplayCollector(BaseCollector)`: `__init__(self, corpus: IssueCorpus)`, 속성 `held: dict[str, str]`, `async search(self, query: SearchQuery) -> list[SearchResult]`(질의 문자열이 `corpus.issue`와 같고 매핑 채널이 `query.channels`에 있는 항목만), `async fetch(self, result: SearchResult) -> RawDocument`.

- [ ] **Step 1: Write the failing tests**:
  - `test_channel_mapping`: NEWS→news, BLOG→blog, CAFE→community, WEB+source_type "NEWS"→news, WEB+"OTHER"→None.
  - `test_undated_and_unmapped_items_are_held_not_returned`: 게시일 없는 BLOG와 WEB/OTHER가 `held == {id1: "undated", id2: "unmapped_channel"}`이고 `search` 결과에 없다.
  - `test_search_only_returns_matching_issue_and_channel`: 다른 질의 문자열이면 `[]`, `channels=[ChannelType.BLOG]`이면 blog 항목만.
  - `test_fetch_builds_raw_document_with_body_flag`: 본문 있는 항목은 `body == item.body`, `metadata["body_available"] is True`; 스니펫만 있는 항목은 `body == snippet`, `body_available is False`; `metadata["kind"]`와 `metadata["source_type"]` 포함; `document_id`는 같은 `result_id`로 두 번 만들어도 동일(`uuid5(NAMESPACE_URL, result_id)`).
  - `test_replay_collector_never_calls_network`: 모듈에 `requests`/`httpx`/`aiohttp` import 없음을 `inspect.getsource`로 검사하지 말고, 대신 `fetch`가 코루틴이 즉시 완료됨(`asyncio.run`)만 확인.
- [ ] **Step 2: Run** the test file → FAIL.
- [ ] **Step 3: Implement** `replay.py`. `source`는 URL의 호스트(`urlsplit(url).netloc` 앞 `www.` 제거), `platform`은 `item.channel.lower()`, `collected_at`은 현재 UTC.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(collectors): add replay collector for pre-searched issue corpora`

---

### Task 3: 적재 워크플로

**Files:**
- Create: `app/workflows/ingest_issue_corpora.py`
- Test: `tests_v2/integration/test_monthly_ingest_sentiment.py` (이 Task에서는 적재 부분만; Task 8에서 확장)

**Interfaces:**
- Consumes: `ReplayCollector`, `partition` (Task 2); `MultiQueryCollectionToEvidenceWorkflow`, `CollectionRequest` (`app/workflows/multi_query_collection_to_evidence.py`); `SqlAlchemyQuerySetRepository.create(project_id, queries)`, `SqlAlchemyProjectRepository`.
- Produces: `async def ingest_corpora(session: Session, project_id: ProjectId, corpora: list[IssueCorpus]) -> dict[str, dict[str, int]]` — 이슈명별 `{"total", "ingestible", "held_undated", "held_unmapped_channel"}`와 키 `"__canonical_documents__"`(`{"count": n}`).

- [ ] **Step 1: Write the failing tests**: 기존 통합 테스트(`tests_v2/integration/`)의 Alembic 마이그레이션된 임시 SQLite·프로젝트 생성 패턴을 그대로 가져온다(`ProjectCreate`로 프로젝트 생성, 상태는 `CREATED`).
  - `test_ingest_counts_add_up_and_issue_becomes_query`: 이슈 1개, 항목 5건(적재 가능 3, 게시일 없음 1, 채널 미매핑 1) → 요약 `total == ingestible + held_undated + held_unmapped_channel`, 적재 문서는 `list_canonical`로 3건, 각 문서의 `query == 이슈명`.
  - `test_same_url_in_fact_and_opinion_is_one_document`: 같은 URL 항목이 서로 다른 `result_id`로 두 번(사실·반응) 들어가면 canonical 문서 1건.
  - `test_all_undated_issue_ingests_nothing_without_error`: 전부 게시일 없음 → 예외 없음, `ingestible == 0`, canonical 0건.
  - `test_two_issues_make_two_queries`: 이슈 2개 → 2.0 질의 2개, 문서의 `query`가 각 이슈명.
- [ ] **Step 2: Run** `./.venv/bin/python -m pytest tests_v2/integration/test_monthly_ingest_sentiment.py -q` → FAIL.
- [ ] **Step 3: Implement** `ingest_corpora`: `SearchQuery(query=issue, channels=[ch])` 목록을 `QuerySetRepository.create`로 저장하고 프로젝트가 `CREATED`면 `QUERIES_READY`로 진행(콘솔 `streamlit_app/console.py` 443-455행과 같은 순서), 이슈마다 적재 가능 항목이 있는 채널별로 `CollectionRequest(collector=ReplayCollector(corpus), query_id=..., run_id=uuid4(), query=...)`를 만들어 워크플로를 한 번 실행한다. 적재할 요청이 하나도 없으면 워크플로를 호출하지 않는다(상태 전이는 하지 않고 요약만 반환).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(workflows): ingest replayed issue corpora through the existing collection workflow`

---

### Task 4: Qwen 문서 감성 분류

**Files:**
- Create: `app/sentiment/document_classifier.py`
- Test: `tests_v2/unit/test_document_sentiment.py`

**Interfaces:**
- Consumes: `app.schemas.document.CleanDocument`; `app.core.enums.SentimentLabel`; `QwenQueryExpansionService.chat(system, user, schema)`.
- Produces:
  - `class SentimentVerdict(SchemaBase)`: `label: SentimentLabel | None`, `evidence: str | None`, `reason: str`, `basis: Literal["BODY","SNIPPET"]` (`metadata["body_available"]`가 참이면 BODY).
  - Qwen 응답 schema(같은 파일, 외부 노출 불필요): 항목 `document_id: str`, `label: Literal["positive","negative","neutral","mixed","unclear"]`, `evidence: str`, `reason: str`.
  - `PROMPT_VERSION = "doc-sentiment-v1"`
  - `async def classify_documents(qwen, issue: str, docs: list[CleanDocument], batch: int = 5) -> dict[DocumentId, SentimentVerdict]`

- [ ] **Step 1: Write the failing tests** with a fake qwen(`async chat(self, system, user, schema, **kw)`가 문서 id별 미리 정한 응답을 돌려줌):
  - `test_positive_label_needs_an_evidence_phrase_that_exists_in_title_or_body`: 근거 구절이 본문에 있으면 `label == POSITIVE`, 없으면 `label is None`이고 `reason`에 "근거"가 들어간다.
  - `test_evidence_matching_ignores_whitespace_and_case`: 줄바꿈·연속 공백만 다른 구절은 인정.
  - `test_neutral_is_accepted_without_evidence_and_unclear_becomes_none`.
  - `test_missing_answers_are_asked_once_more_then_left_unclassified`: 첫 응답이 5건 중 3건만 → 누락 2건 재요청; 두 번째에도 없으면 `label is None`, `reason == "qwen_no_answer"`.
  - `test_a_failing_batch_leaves_its_documents_unclassified_with_reason`: `chat`이 예외 → 해당 배치 전부 `reason == "qwen_failed"`, 다른 배치는 정상.
  - `test_snippet_only_documents_are_marked_basis_snippet`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** 프롬프트는 이슈명·문서 제목·본문(앞 1500자)만 근거로 쓰고, 본문에 없는 말을 쓰지 말고 근거 구절을 글자 그대로 복사하게 한다. "글쓴이·기사가 이슈를 어떻게 평가하는가(긍정/부정/중립/혼재)"만 판정하고, 단순 사건 나열은 neutral로 두게 한다. 근거 확인은 제목+본문을 공백 제거·casefold한 문자열에 구절이 포함되는지로 한다. 재요청 패턴은 `app/search/opinion.py::_ask_all`과 같으나 그 함수는 `result_id` 속성에 묶여 있어 쓰지 않고 같은 모양으로 새로 쓴다.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(sentiment): classify documents with Qwen and verify evidence phrases in code`

---

### Task 5: 분류 결과 저장과 프로젝트 단위 실행

**Files:**
- Modify: `app/sentiment/document_classifier.py`
- Test: `tests_v2/unit/test_document_sentiment.py`, `tests_v2/integration/test_monthly_ingest_sentiment.py`

**Interfaces:**
- Consumes: `classify_documents`, `SentimentVerdict` (Task 4); `SqlAlchemyDocumentRepository.list_canonical/upsert_clean`.
- Produces:
  - `def store_sentiment(repo: DocumentRepository, project_id: ProjectId, document: CleanDocument, verdict: SentimentVerdict, *, model: str) -> bool` — 기존 `document.metadata`에 `sentiment`(라벨 있을 때만), `sentiment_evidence`, `sentiment_reason`, `sentiment_basis`, `sentiment_model`, `sentiment_prompt_version`, `sentiment_review="AI_ONLY"`를 병합해 `upsert_clean`. `sentiment_review`가 `"AGREED"`/`"CORRECTED"`면 쓰지 않고 `False`.
  - `async def classify_project(qwen, session: Session, project_id: ProjectId) -> dict[str, int]` — 키: `positive`, `negative`, `neutral`, `mixed`, `unclassified`, `skipped_reviewed`. 문서는 `document.query`(이슈명)별로 묶어 `classify_documents`에 넘긴다.

- [ ] **Step 1: Write the failing tests**:
  - `test_store_merges_metadata_and_keeps_existing_keys`: 기존 `{"body_available": True}`가 저장 후에도 남는다(단위, 가짜 repo가 `upsert_clean` 인자를 기록).
  - `test_unclassified_verdict_writes_no_sentiment_key` — 라벨 `None`이면 `"sentiment"` 키가 없고 사유는 저장된다.
  - `test_reviewed_documents_are_not_overwritten`: `sentiment_review == "CORRECTED"`이면 `store_sentiment`가 `False`, repo 호출 없음.
  - 통합 `test_classify_project_writes_labels_the_analytics_reads`: Task 3의 적재 결과에 가짜 qwen으로 분류 실행 → 반환 건수 합계 == canonical 문서 수, DB에서 읽은 `metadata["sentiment"]` 값이 `SentimentLabel` 값 중 하나이고 `unclassified` 문서에는 키가 없다.
  - 통합 `test_rerun_keeps_other_metadata`: 분류를 두 번 돌려도 `body_available`/`kind` 메타데이터가 유지된다.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** both functions. 모델명은 `qwen.model`, 프롬프트 버전은 `PROMPT_VERSION`.
- [ ] **Step 4: Run** both test files → PASS.
- [ ] **Step 5: Commit** `feat(sentiment): store document sentiment through the document repository`

---

### Task 6: 검수 표본과 검수 기록

**Files:**
- Create: `app/sentiment/review.py`
- Test: `tests_v2/unit/test_sentiment_review.py`

**Interfaces:**
- Consumes: `CleanDocument` 목록(메타데이터에 Task 5의 키), `DocumentRepository.upsert_clean`.
- Produces:
  - `SAMPLE_FLOOR = 20`, `SAMPLE_CAP = 40`, `SAMPLE_RATIO = 0.2`
  - `def sample_size(total: int) -> int` — `min(total, SAMPLE_CAP, max(SAMPLE_FLOOR, ceil(SAMPLE_RATIO * total)))`
  - `def select_review_sample(docs: list[CleanDocument]) -> list[DocumentId]` — 이슈(`document.query`)별로 `sample_size`만큼, `sha1(str(document_id))` 순서로 결정적 선택(분류된 문서와 미분류 문서 모두 포함).
  - `def record_review(repo, project_id, document: CleanDocument, *, label: SentimentLabel | None) -> None` — AI 라벨과 같으면 `sentiment_review="AGREED"`, 다르면 `"CORRECTED"`(`sentiment_ai_label`에 기존 값 보존, `sentiment`는 새 라벨; `None`이면 `sentiment` 키 제거) 로 병합 저장.
  - `def review_summary(docs: list[CleanDocument]) -> dict[str, dict[str, int]]` — 이슈별 `{"sample", "reviewed", "agreed", "corrected"}`; `sample`은 `select_review_sample` 크기.

- [ ] **Step 1: Write the failing tests**: 
  - `test_sample_size_rules`: `sample_size(10) == 10`, `(60) == 20`, `(150) == 30`, `(500) == 40`, `(0) == 0`.
  - `test_selection_is_deterministic_and_per_issue`: 같은 입력을 두 번 → 같은 결과; 이슈 2개면 각각 따로 뽑힘.
  - `test_record_review_agreed_and_corrected_keep_ai_label`.
  - `test_summary_counts_only_reviewed_documents_in_the_sample` — 검수 표본 밖 문서를 검수해도 `reviewed`는 표본 안 문서만 센다.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `review.py`(Task 5와 같은 메타데이터 병합 규칙).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(sentiment): add review sampling and review records`

---

### Task 7: 검수 화면

**Files:**
- Create: `streamlit_app/sentiment_review.py`
- Modify: `streamlit_app/console.py` (메뉴/라우팅: `page_analytics`가 등록된 1416행 부근 패턴을 따라 새 항목 한 줄 추가)
- Test: `tests_v2/unit/test_sentiment_review_page.py`

**Interfaces:**
- Consumes: `select_review_sample`, `record_review`, `review_summary` (Task 6), 세션 팩토리 `session_scope`.
- Produces: `def render_review(docs: list[CleanDocument], summary: dict, on_decide) -> None`(순수 렌더, 폴링 없음), `def page_sentiment_review(factory: sessionmaker) -> None`.

- [ ] **Step 1: Write the failing test** (`AppTest.from_function`, 기존 `test_analytics_ui.py`처럼 래퍼 안에서 import):
  - `test_page_shows_ai_label_evidence_and_sample_progress`: 문서 제목, AI 라벨, 근거 구절, "검수 N / 표본 M"이 보인다.
  - `test_agree_and_correct_buttons_call_the_decision_callback_with_expected_label`.
  - `test_docs_without_sample_show_empty_state`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** 카드에 이슈명, 제목·원문 링크, 본문 확보 여부(스니펫만이면 "스니펫 기준" 표시), AI 라벨, 근거 구절을 보이고 "동의"/"긍정·부정·중립·혼재·미분류로 수정" 버튼을 둔다. 결정은 `on_decide(document, label)`로 넘겨 `page_sentiment_review`가 `record_review`를 호출한다.
- [ ] **Step 4: Run** the new test and `tests_v2/unit/test_analytics_ui.py` → PASS.
- [ ] **Step 5: Commit** `feat(ui): add sentiment sample review page`

---

### Task 8: 적재→분류→Analytics 통합 검증

**Files:**
- Modify: `tests_v2/integration/test_monthly_ingest_sentiment.py`

**Interfaces:** Consumes: Task 3·5의 함수들, 기존 `EvidenceToIssuesWorkflow`/`AnalyticsService`(기존 통합 테스트에서 호출하는 방식을 그대로 따른다).

- [ ] **Step 1: Write the failing test** `test_corpus_to_sentiment_distribution`: 이슈 2개 코퍼스(게시일 있는 문서 6건, 게시일 없는 1건, 가짜 qwen이 긍정 2·부정 1·중립 1·근거 불일치로 미분류 2건을 돌려줌) → 적재 → 분류 → Analytics 실행 후 `sentiment_distribution`이 `{"positive": 2, "negative": 1, "neutral": 1, "mixed": 0, "unclassified": 2}`이고 합이 canonical 문서 수와 같다. 보류 1건은 어떤 집계에도 들어가지 않는다.
- [ ] **Step 2: Run** `./.venv/bin/python -m pytest tests_v2/integration/test_monthly_ingest_sentiment.py -q` → FAIL.
- [ ] **Step 3: Fix** whatever integration gap the test reveals (코드 변경이 필요하면 해당 Task의 모듈에서 수정).
- [ ] **Step 4: Run** the full suite: `XDG_CACHE_HOME=/tmp/aiporg_cache MPLCONFIGDIR=/tmp/aiporg_mpl ./.venv/bin/python -m pytest tests_v2 tests -q` → 모두 통과(실패가 있으면 다음 단계 진행 금지).
- [ ] **Step 5: Commit** `test(integration): verify corpus ingestion to sentiment distribution`

---

### Task 9: 기록

**Files:**
- Modify: `HANDOFF.md`, `docs/superpowers/plans/2026-11-17-aiporg-v1-implementation.md`

- [ ] **Step 1:** `HANDOFF.md`에 이번 단계 결과(구현 범위, 테스트 통과 수, 남은 것: 프로젝트 4·5, 실제 Qwen 분류 품질 미측정, 코퍼스를 만드는 end-to-end 실행기 부재)를 갱신한다. 계획서 Phase 4의 해당 체크박스를 갱신한다.
- [ ] **Step 2: Run** `git diff --check` → 출력 없음.
- [ ] **Step 3: Commit and push** `docs(handoff): record monthly ingestion and sentiment step`

---

## Self-Review 결과

- **스펙 범위 확인:** §5.2의 1(코퍼스·적재)=Task 1~3, 2(분류)=Task 4~5, 3(검수)=Task 6~7, 검증 기준 첫째(적재+보류=전체)=Task 3, 둘째·셋째=프로젝트 4에서 다룸, 감성 근거 규칙=Task 4. §7의 메타데이터 병합 확인 사항은 Global Constraints와 Task 5에서 처리. 프로젝트 4·5는 의도적으로 제외.
- **알려진 공백:** 현재 저장소에는 검색→분석→세션을 한 번에 돌리는 실행기가 없어(세션은 임시 스크립트로 생성) `build_corpus`를 호출하는 곳이 이 계획에 없다. 실제 월간 사용 전에 end-to-end 실행기(계획서 Phase 5)가 필요하다. 기존 세션 3개에는 게시일이 없어 이 계획의 적재에서는 전부 보류된다.
- **실제 Qwen 분류 품질**은 이 계획의 테스트(가짜 qwen)로 검증되지 않는다. Task 8 이후 한 이슈로 실측한다.
