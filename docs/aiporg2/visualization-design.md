# Visualization/Report 출력·승인 계약 결정 (M0, 2b/2c)

작성: 2026-10-18. 상태: **결정·구현 완료(1차 최소 단위: VIS-02 채널 도넛, VIS-07
TOP10 카드만)**. `docs/superpowers/plans/2026-09-08-aiporg2-implementation.md`
"2. 데이터 계약·저장 구조 변경안"의 (b) Visualization, (c) Report 제안을
`narrative-design.md`가 Narrative 출력에 썼던 것과 같은 절차(기존 계약은
그대로 두고 새 모델만 추가, 기존 DB JSON envelope 재사용)로 구체화한 결정
기록이다.

## 왜 기존 `VisualizationAssetSchema`/`ReportSchema`를 바꾸지 않는가

`tests_v2/contracts/test_fact_schema_contract.py`가
`VisualizationAssetSchema`의 필드 집합을 `model_fields == {...}`로 그대로
고정하고, `ReportSchema.context`가 정확히 `NarrativeContext` 모양이어야
통과하는 라운드트립 테스트를 갖고 있다. 이는 AGENTS.md 1·2번 규칙(임의
schema 추가 금지, 기존 Pydantic model 이름 변경 금지)이 코드로 이미
강제되고 있다는 뜻이다. 그래서 이번 결정도 Narrative 출력 계약 때와 같은
원칙을 따른다: **기존 두 모델은 한 글자도 바꾸지 않고, 완전히 새로운
출력 모델을 추가한다.** 기존 `VisualizationAssetSchema`/`Visualization.create()`는
이제 "Report에 포함된 시각 자료의 가벼운 식별자(id/kind/title)" 역할만
계속하고, 실제 편집 가능한 데이터·승인 상태는 새 출력 모델이 담당한다.

## 결정 1: `VisualizationOutputSchema` (신규, additive)

`app/schemas/visualization.py`에 `VisualizationAssetSchema`는 그대로 두고
아래 두 모델을 추가한다.

```python
class VisualizationItemSchema(SchemaBase):
    label: str
    value: int  # >= 0
    analytics_path: str  # 예: "metrics.channel_mentions.NEWS" — 근거 경로, 비어있을 수 없음
    category: str | None = None
    color: str | None = None
    order: int
    included: bool = True


class VisualizationOutputSchema(SchemaBase):
    project_id: ProjectId
    run: VersionedRunSchema
    analytics_run_id: RunId
    slot_key: str          # 어떤 시각 자료인지("channel_donut", "top10_keywords")
    kind: str               # "chart" | "cards" 등
    title: str
    items: list[VisualizationItemSchema]
    approved: bool = False
    approved_at: datetime | None = None
```

- `value`는 AnalyticsSnapshot.metrics에서 그대로 읽은 집계값이며 UI에서
  직접 타이핑으로 바꿀 수 없다(AGENTS.md 7번 "numeric value는 evidence
  없는 경우 생성 금지" — 집계값 변경은 재집계를 통해서만 가능해야 한다는
  요구사항 §8.1 "원자료/분류/집계 조건의 수정으로 연결"을 그대로 반영).
  UI에서 수정 가능한 것은 `label`(표시 문구), `category`, `color`,
  `order`, `included`뿐이다 — 요구사항 §8.1 표의 "차트" 행(제목, 계열
  선택=included, 정렬=order, 색상, 범례=label)과 정확히 일치한다.
- `analytics_path`가 비어 있으면 안 된다(Narrative 문장의 "근거 최소 1개"
  검증과 동일한 원칙).
- `slot_key`로 같은 프로젝트 안의 여러 시각 자료(채널 도넛과 TOP10 카드)를
  구분한다. Narrative 출력은 프로젝트당 "한 흐름"이라 슬롯이 필요 없었지만
  시각 자료는 여러 종류가 동시에 존재하므로 Narrative 설계에 없던 필드다.
- 매 수정·재생성은 새 `run`(새 row)으로 저장한다(Narrative와 동일 패턴).
  승인 상태는 **그 버전에 종속**된다 — 새 버전은 항상 `approved=False`로
  시작한다(§8.1 "승인 후 변경한 자료는 재검수 상태").

## 결정 2: 저장 — 기존 `visualizations.payload` JSON을 envelope로 재사용

`Visualization` 모델에는 이미 쓰이지 않는 `payload: JSON` 컬럼이 있었다
(기존 `create()`가 항상 `payload={}`로 채워넣고 있었음). 새 테이블을 만들지
않고 이 컬럼에 Narrative와 동일한 `{"kind": "visualization_output", "data": {...}}`
envelope로 저장한다. 기존 `create()`/`list_by_project()`(식별자 전용 row)는
그대로 두고, `list_by_project()`는 envelope row를 건너뛰도록 한 줄만
고친다(Narrative의 `get_latest()`가 출력 row를 건너뛰는 것과 동일 원리).

`VisualizationRepository`에 추가하는 메서드(기존 `create`/`list_by_project`는
시그니처 변경 없음):

- `save_output(project_id, output) -> VisualizationOutputRead` — 새 row insert.
- `get_latest_output(project_id, slot_key) -> VisualizationOutputRead | None` —
  해당 slot의 최신 버전(각 출력이 자기 `run.created_at`을 들고 있어서 비교에
  씀 — SQLite `CURRENT_TIMESTAMP` 1초 해상도 문제, Narrative에서 이미 겪은
  것과 동일).
- `list_outputs(project_id, slot_key) -> list[VisualizationOutputRead]` — 버전
  이력 전체(최신순).
- `approve_output(project_id, run_id, approved, approved_at) -> VisualizationOutputRead` —
  **새 버전을 만들지 않고 같은 row를 그대로 갱신**한다. 승인/승인취소는
  내용을 바꾸는 게 아니라 메타데이터만 바꾸는 작업이라 새 버전을 만들
  이유가 없다(기존 `CollectionRunRepository.complete()`가 같은 PK row를
  제자리에서 갱신하는 것과 동일한 전례 — append-only가 이 코드베이스의
  절대 규칙은 아니다).

`NarrativeRepository`에도 같은 이유로 `approve_output(project_id, run_id,
approved, approved_at)`을 추가한다. `NarrativeOutputSchema`에
`approved: bool = False`, `approved_at: datetime | None = None` 두 필드를
추가한다(기존 필드·테스트는 전부 기본값으로 호환 — `test_narrative_output_schema.py`에
라운드트립 전체 비교 테스트가 없음을 확인했다).

## 결정 3: "최종 승인"은 새 schema 없이 기존 Report를 조립하는 서비스로 구현

요구사항 §8.1 "포함된 모든 자료의 현재 버전이 승인되어야 최종 보고서를
승인·출력한다"를 **`ReportSchema`/`Report` 테이블에 아무 필드도 추가하지
않고** 구현한다. `Report` row가 존재한다는 사실 자체가 "그 순간 그 버전들이
전부 승인됐다"는 증거이기 때문에, 승인 플래그를 Report에 따로 둘 필요가
없다.

새 `app/report/approval.py::ReportApprovalService`(LLM 호출·웹 요청·직접
DB write 없음 — 기존 repository만 사용)가 한다:

1. `NarrativeRepository.get_latest_output()`이 있고 `approved=True`인지 확인.
2. 필수 슬롯(`REQUIRED_VISUALIZATION_SLOTS = ("channel_donut",
   "top10_keywords")`) 각각에서 `get_latest_output(slot_key)`이 있고
   `approved=True`인지 확인.
3. 하나라도 없거나 미승인이면 `ReportApprovalError`(어느 슬롯/narrative가
   빠졌는지 담음)를 던지고 Report를 만들지 않는다.
4. 전부 통과하면, 각 승인된 시각 자료마다 `VisualizationRepository.create()`로
   식별자 row(기존 `VisualizationAssetSchema`, 변경 없음)를 새로 등록하고,
   `NarrativeRepository.get_latest()`(기존 입력 `NarrativeContext`)와
   함께 `ReportSchema`를 조립해 `ReportRepository.create()`로 저장한다.

### 알려진 범위 제한(의도적으로 다음으로 미룸)

`ReportSchema.context`는 여전히 `NarrativeContext`(입력)이고, 사용자가
실제로 승인한 문장(`NarrativeOutputSchema.sentences`)을 아직 Report 안에
담지 않는다 — `narrative-design.md`가 8차에서 이미 지적한 간극이다.
`ReportSchema`에 `narrative_output` 같은 필드를 additive로 추가하는 안을
검토했지만, 이번 1차 최소 단위(채널 도넛+TOP10 카드 승인 흐름을 끝까지
연결하는 것)의 필수 조건은 아니라고 판단해 범위에서 뺐다. 승인된 문장은
`NarrativeRepository.get_latest_output()`으로 언제든 조회 가능하므로
데이터가 사라지는 건 아니다 — Report가 narrative 서술 자체를 번들링하는
문제는 HWPX/DOCX 실제 조립(M5/M6) 작업 때 다시 결정한다.

## 결정 4: 1차 시각 자료 2종의 데이터 출처

`app/analytics/service.py::AnalyticsService.build()`가 만드는
`AnalyticsSnapshotSchema.metrics`에서 그대로 가져온다(Analyzer 쪽을 건드리지
않음, AGENTS.md 5번 "Analyzer에서 웹 요청 금지"와 무관하게 사용만 함):

- **VIS-02 채널 도넛** (`slot_key="channel_donut"`, `kind="chart"`): 입력은
  `metrics["channel_mentions"]`(채널→건수)와 `metrics["channel_document_ids"]`
  (채널→문서ID 목록, `analytics_path` 근거용). 항목마다
  `analytics_path=f"metrics.channel_mentions.{channel}"`.
- **VIS-07 TOP10 카드** (`slot_key="top10_keywords"`, `kind="cards"`): 입력은
  `metrics["keyword_frequencies"]`(키워드→건수)에서 상위 10개(건수 내림차순,
  동률은 키워드 사전순)와 `metrics["keyword_document_ids"]`.
  `analytics_path=f"metrics.keyword_frequencies.{keyword}"`.

새 `app/visualization/service.py::VisualizationRenderService`가 이 매핑만
한다 — 결정론적, 집계값 그대로, 이미지 생성 모델 호출 없음(요구사항 §6.1
원칙 그대로).

## Streamlit 연결

"6. 시각 자료 편집·승인" 신규 화면(§8 표 그대로)에서 두 슬롯 각각 생성·
재생성, 버전 선택·비교, 항목별 label/color/order/included 수정 후 저장(새
버전), 승인/승인취소(최신 버전에서만 활성화)를 제공한다. "5. 서술 편집"의
비활성화해뒀던 "최종 승인" 버튼을 narrative `approve_output`에 연결하고,
narrative+두 슬롯이 전부 승인된 경우에만 활성화되는 "보고서 생성(최종
승인)" 버튼을 추가해 `ReportApprovalService`를 호출한다.

## 이번 결정 범위 밖(다음 결정 대상)

- VIS-01, 03~06, 08, 09 및 일반 표 — 이번엔 VIS-02/07만.
- `ReportSchema`에 승인된 narrative 문장을 실제로 번들링하는 문제(위 "알려진
  범위 제한" 참고).
- 시각 자료의 실제 PNG 렌더링과 HWPX 삽입 — Streamlit 미리보기는 구조화된
  데이터를 그대로 그리고(표/간단한 막대), 실제 300dpi 이미지 렌더링은 HWPX
  시제품 작업에서 필요한 만큼만 먼저 만든다.
- 공식 출처 정책(기존 미해결 사항, 이번 작업과 무관).
