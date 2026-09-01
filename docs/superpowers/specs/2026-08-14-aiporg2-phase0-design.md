# AIPORG 2.0 Phase 0 Design

## Goal

AIPORG 1.0과 충돌하지 않는 별도 경계 안에서 AIPORG 2.0의 기초 도메인 구조를 확정한다.  
이번 Phase 0의 범위는 PRD에 정의된 core schema, SQLAlchemy model, repository contract, workflow state machine, migration baseline, contract test까지로 제한한다.

## Scope

포함:

- `Project` 중심 도메인 모델
- Pydantic schema 정의
- SQLAlchemy persistence model 정의
- repository interface 정의
- workflow state machine 정의
- Alembic 초기 migration 설계
- schema contract test, state machine test

제외:

- collector 구현
- cleaning 구현
- evidence 추출 구현
- issue discovery 구현
- analytics 구현
- LLM provider 구현
- visualization, report 구현
- 실제 외부 API 연동

## Primary Decision

AIPORG 2.0은 기존 `aiporg/` 패키지를 확장하지 않고, 새 루트 `app/` 아래 독립 구현한다.

이 결정의 이유:

1. 기존 1.0의 CLI, 테스트, 모델과 import 충돌을 피할 수 있다.
2. PRD가 요구한 `app/core`, `app/models`, `app/schemas`, `app/repositories` 구조를 그대로 반영할 수 있다.
3. 2.0 전용 workflow state machine과 versioned JSON contract를 1.0과 분리해 고정할 수 있다.

## Alternatives Considered

### Option A: `app/` 병행 구조

기존 `aiporg/`는 그대로 유지하고, 2.0을 `app/` 아래 새 계층으로 구축한다.

장점:

- PRD 일치도가 가장 높다.
- 1.0 보호가 쉽다.
- 이후 FastAPI, collectors, analytics를 단계적으로 추가하기 좋다.

단점:

- 레포 내에 두 시스템이 공존해 구조가 커진다.

### Option B: `aiporg2/` 새 패키지

장점:

- Python package naming은 단순하다.

단점:

- PRD의 폴더 구조와 어긋난다.
- 추후 계층 분리가 다시 필요할 가능성이 높다.

### Option C: 별도 레포 분리

장점:

- 물리적 충돌 가능성이 가장 낮다.

단점:

- 현재 레포 자산과의 비교, 이행, 테스트 공용화가 번거롭다.

권장안은 Option A다.

## Physical Layout

Phase 0 기준 신규 구조:

```text
app/
  core/
    config.py
    enums.py
    logging.py
    state_machine.py

  models/
    base.py
    project.py
    collection.py
    document.py
    evidence.py
    fact.py
    issue.py
    analytics.py
    narrative.py
    visualization.py
    report.py

  schemas/
    common.py
    project.py
    query.py
    collection.py
    document.py
    evidence.py
    fact.py
    issue.py
    analytics.py
    narrative.py
    visualization.py
    report.py

  repositories/
    base.py
    project.py
    collection.py
    document.py
    fact.py
    issue.py
    analytics.py
    report.py

alembic_v2/
tests_v2/
  contracts/
  unit/
docs/aiporg2/
```

기존 `aiporg/`, `tests/`, `config/`는 1.0으로 간주하고 Phase 0에서 수정하지 않는다.

## Architectural Boundaries

### 1. Domain-first

Collector, analyzer, writer보다 먼저 schema와 persistence contract를 고정한다.

### 2. Engine isolation

다음 7개 엔진은 별도 모듈로 유지한다.

```text
1. Collector Engine
2. Evidence Engine
3. Issue Engine
4. Analytics Engine
5. Narrative Engine
6. Visualization Engine
7. Report Engine
```

각 엔진은 다른 엔진의 내부 구현을 직접 참조하지 않는다. 데이터 이동은 DB 또는 versioned JSON contract만 허용한다.

### 3. Repository-only persistence

Collector나 analyzer는 DB에 직접 write하지 않는다. SQLAlchemy session 접근은 repository layer를 통해서만 허용한다.

### 4. Contract stability

PRD에 정의된 핵심 필드명은 Phase 0 이후 변경하지 않는다. 특히 다음 필드명은 고정한다.

- `published_at`
- `project_id`
- `comparison_period`
- `collection_run`
- `document_id`
- `canonical_url`

## Domain Model

최상위 aggregate는 `Project`다.

```text
Project
├── Target
├── QuerySet
├── CollectionRuns
├── Documents
├── Evidence
├── Facts
├── Issues
├── Analytics
├── Narratives
├── Visualizations
└── Reports
```

### Core entities for Phase 0

- `Project`
- `QuerySet`
- `CollectionRun`
- `Document`
- `DuplicateCluster`
- `Evidence`
- `Fact`
- `NumericFact`
- `Issue`
- `IssueDetail`
- `AnalyticsSnapshot`
- `Narrative`
- `Visualization`
- `Report`

## Schema Design

Pydantic v2 schema는 다음 원칙을 따른다.

1. 외부 계약용 schema와 DB model을 분리한다.
2. 모든 날짜 필드는 ISO 8601 문자열 또는 timezone-aware datetime으로 normalize 가능해야 한다.
3. channel, status, sentiment는 enum으로 제한한다.
4. optional metadata는 `metadata` 객체 아래 유지한다.
5. versioned output에는 `input_version`, `output_version`, `run_id`를 둔다.

### High-value schema set

- `ProjectCreate`
- `ProjectRead`
- `TargetSchema`
- `AnalysisPeriodSchema`
- `ComparisonPeriodSchema`
- `SearchQuery`
- `SearchResult`
- `RawDocument`
- `CleanDocument`
- `DuplicateClusterSchema`
- `EvidenceSchema`
- `FactSchema`
- `NumericFactSchema`
- `IssueCandidateSchema`
- `IssueSchema`
- `NarrativeContext`
- `VisualizationAssetSchema`
- `ReportSchema`

## Persistence Model

SQLAlchemy model은 PostgreSQL 기준으로 설계하고, 로컬 SQLite에서도 동작 가능하도록 구현한다.

### Required tables in Phase 0

- `projects`
- `query_sets`
- `queries`
- `collection_runs`
- `documents`
- `duplicate_clusters`
- `document_duplicates`
- `evidence`
- `facts`
- `numeric_facts`
- `issues`
- `issue_facts`
- `analytics_snapshots`
- `narratives`
- `visualizations`
- `reports`

### Key constraints

- `projects.id` UUID PK
- `documents(project_id, canonical_url)` unique
- `documents.url_hash` unique within project scope
- `collection_runs` has status enum
- `facts.status` has enum
- `reports.project_id` FK to `projects.id`
- many-to-many bridge tables for issue-fact, evidence-document mapping

## Workflow State Machine

상태는 PRD 기준으로 고정한다.

```text
CREATED
→ QUERIES_READY
→ COLLECTION_RUNNING
→ COLLECTION_COMPLETED
→ CLEANING_COMPLETED
→ EVIDENCE_COMPLETED
→ ISSUES_COMPLETED
→ ANALYTICS_COMPLETED
→ NARRATIVE_COMPLETED
→ VISUALS_COMPLETED
→ REPORT_COMPLETED
```

### Transition rules

- 이전 단계 완료 전 다음 단계 진입 금지
- 실패 상태는 각 run 단위에서 관리하고, project workflow state는 마지막 성공 기준으로만 전진
- upstream output version이 바뀌면 downstream artifact는 stale로 간주

### Re-run model

각 단계 결과는 다음 키를 가진다.

- `run_id`
- `input_version`
- `output_version`
- `created_at`

이를 통해 `collection:v3`, `evidence:v2` 같은 재실행 이력을 저장한다.

## Repository Contract

Repository는 interface 우선으로 정의한다.

### Base principles

- service는 repository interface만 의존한다.
- repository가 session lifecycle을 캡슐화한다.
- collector/analyzer/writer는 ORM model을 직접 commit하지 않는다.

### Initial repository set

- `ProjectRepository`
- `QuerySetRepository`
- `CollectionRunRepository`
- `DocumentRepository`
- `DuplicateClusterRepository`
- `EvidenceRepository`
- `FactRepository`
- `IssueRepository`
- `AnalyticsRepository`
- `NarrativeRepository`
- `VisualizationRepository`
- `ReportRepository`

### Contract examples

- `ProjectRepository.create(project: ProjectCreate) -> ProjectRead`
- `CollectionRunRepository.start(...) -> CollectionRunRead`
- `DocumentRepository.upsert_raw(document: RawDocument) -> DocumentRead`
- `FactRepository.save_batch(facts: list[FactSchema]) -> list[FactRead]`
- `ReportRepository.create(report: ReportSchema) -> ReportRead`

## Testing Strategy

Phase 0 테스트는 구현 기능보다 계약 안정성 검증에 집중한다.

### Contract tests

- Pydantic schema field name regression 방지
- enum 허용값 검증
- required/optional field 구분 검증
- JSON serialization shape 검증

### Unit tests

- workflow state transition 허용/차단
- repository protocol conformance
- UUID/date normalization helper

### Migration tests

- empty database에서 initial migration 적용 가능
- SQLite test DB와 PostgreSQL dialect 모두에서 metadata build 가능

## Error Handling

Phase 0에서는 structured exception hierarchy만 정의한다.

- `DomainValidationError`
- `InvalidStateTransitionError`
- `RepositoryConflictError`
- `ContractVersionError`

네트워크 오류, collector timeout 등은 이후 Phase에서 collector-specific error로 분리한다.

## Non-goals

이번 단계에서는 다음을 하지 않는다.

- 검색 결과 수집
- 본문 파싱
- 감성 분석
- 이슈 클러스터링
- 추천문 생성
- DOCX/PDF 렌더링

## Ambiguities To Resolve Later

다음 항목은 PRD상 방향은 있으나, Phase 0에서 구체 동작을 임의로 결정하지 않는다.

1. `Evidence`와 `Fact`의 다대다 매핑 세부 구조
2. `AnalyticsSnapshot`의 세분화 단위
3. `Narrative`와 `SourceMapping`의 테이블 분리 여부
4. PostgreSQL enum을 Alembic에서 공용 타입으로 관리할지 여부
5. `duplicate_clusters`의 canonical document 선출 정책

## Implementation Guardrails

Phase 0 구현 시 반드시 지킬 규칙:

1. collector code 추가 금지
2. 외부 HTTP 요청 금지
3. LLM provider 구현 금지
4. numeric value 추정 금지
5. 1.0 package import 수정 금지
6. `AGENTS.md`에 2.0 개발 금칙사항 명시

## Success Criteria

Phase 0 완료 기준:

- PRD field name과 일치하는 core schema 존재
- SQLAlchemy model과 Alembic baseline 존재
- repository interface 존재
- workflow state machine 존재
- contract tests 존재
- 1.0 코드 경로와 import 충돌 없음
