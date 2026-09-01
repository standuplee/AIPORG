# AIPORG 2.0 Phase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AIPORG 1.0과 분리된 `app/` 기반 AIPORG 2.0의 core domain schema, persistence model, repository contract, workflow state machine, Alembic baseline, contract test를 구축한다.

**Architecture:** 기존 `aiporg/`는 그대로 두고, 2.0은 `app/` 아래 별도 계층으로 구성한다. 구현은 domain contract를 먼저 고정하고, 그 위에 SQLAlchemy model, repository protocol, state machine, migration, contract test를 순차적으로 올린다.

**Tech Stack:** Python 3.12, Pydantic v2, SQLAlchemy, Alembic, pytest, mypy

---

## File Structure

### New files

- `AGENTS.md`
- `app/__init__.py`
- `app/core/__init__.py`
- `app/core/enums.py`
- `app/core/state_machine.py`
- `app/core/config.py`
- `app/core/logging.py`
- `app/schemas/__init__.py`
- `app/schemas/common.py`
- `app/schemas/project.py`
- `app/schemas/query.py`
- `app/schemas/collection.py`
- `app/schemas/document.py`
- `app/schemas/evidence.py`
- `app/schemas/fact.py`
- `app/schemas/issue.py`
- `app/schemas/analytics.py`
- `app/schemas/narrative.py`
- `app/schemas/visualization.py`
- `app/schemas/report.py`
- `app/models/__init__.py`
- `app/models/base.py`
- `app/models/project.py`
- `app/models/collection.py`
- `app/models/document.py`
- `app/models/evidence.py`
- `app/models/fact.py`
- `app/models/issue.py`
- `app/models/analytics.py`
- `app/models/narrative.py`
- `app/models/visualization.py`
- `app/models/report.py`
- `app/repositories/__init__.py`
- `app/repositories/base.py`
- `app/repositories/project.py`
- `app/repositories/collection.py`
- `app/repositories/document.py`
- `app/repositories/evidence.py`
- `app/repositories/fact.py`
- `app/repositories/issue.py`
- `app/repositories/analytics.py`
- `app/repositories/narrative.py`
- `app/repositories/visualization.py`
- `app/repositories/report.py`
- `alembic_v2.ini`
- `alembic_v2/env.py`
- `alembic_v2/script.py.mako`
- `alembic_v2/versions/20260814_000001_initial_phase0.py`
- `tests_v2/__init__.py`
- `tests_v2/contracts/__init__.py`
- `tests_v2/contracts/test_project_schema_contract.py`
- `tests_v2/contracts/test_document_schema_contract.py`
- `tests_v2/contracts/test_fact_schema_contract.py`
- `tests_v2/contracts/test_issue_schema_contract.py`
- `tests_v2/unit/__init__.py`
- `tests_v2/unit/test_state_machine.py`
- `tests_v2/unit/test_repository_protocols.py`
- `tests_v2/unit/test_sqlalchemy_metadata.py`

### Existing files to reference only

- `requirements.txt`
- `docs/superpowers/specs/2026-08-14-aiporg2-phase0-design.md`

## Task 1: Lock 2.0 Guardrails

**Files:**
- Create: `AGENTS.md`
- Test: none

- [ ] **Step 1: Write the guardrail document**

Add the 2.0 rules from the PRD:

```md
1. 임의 schema 추가 금지.
2. 기존 Pydantic model 이름 변경 금지.
3. Repository 외 직접 DB write 금지.
4. Collector에서 LLM 호출 금지.
5. Analyzer에서 웹 요청 금지.
6. Writer에서 새로운 fact 생성 금지.
7. numeric value는 evidence 없는 경우 생성 금지.
8. 모든 module 변경 시 unit test 작성.
9. integration test 실패 시 다음 기능 구현 금지.
```

- [ ] **Step 2: Verify the file content**

Run: `sed -n '1,120p' AGENTS.md`
Expected: the nine rules are present and readable.

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs: add aiporg 2.0 guardrails"
```

## Task 2: Define Core Enums and Workflow State Machine

**Files:**
- Create: `app/__init__.py`
- Create: `app/core/__init__.py`
- Create: `app/core/enums.py`
- Create: `app/core/state_machine.py`
- Test: `tests_v2/unit/test_state_machine.py`

- [ ] **Step 1: Write the failing state machine tests**

Add tests for:

```python
def test_created_can_transition_to_queries_ready(): ...
def test_cannot_skip_collection_running(): ...
def test_report_completed_has_no_forward_transition(): ...
def test_invalid_transition_raises_error(): ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests_v2/unit/test_state_machine.py -v`
Expected: FAIL because `app.core.state_machine` does not exist yet.

- [ ] **Step 3: Implement enums**

Create enums for:

- `WorkflowState`
- `CollectionRunStatus`
- `FactStatus`
- `ChannelType`
- `SentimentLabel`
- `ConfidenceGrade`

- [ ] **Step 4: Implement the state machine**

Implement:

```python
class WorkflowStateMachine:
    def can_transition(self, current: WorkflowState, target: WorkflowState) -> bool: ...
    def require_transition(self, current: WorkflowState, target: WorkflowState) -> None: ...
```

Rules:

- only next-step transitions allowed
- no backward transitions in Phase 0
- invalid transition raises `InvalidStateTransitionError`

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests_v2/unit/test_state_machine.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/core app/__init__.py tests_v2/unit/test_state_machine.py
git commit -m "feat: add aiporg 2.0 workflow state machine"
```

## Task 3: Define Common and Project Schemas

**Files:**
- Create: `app/schemas/__init__.py`
- Create: `app/schemas/common.py`
- Create: `app/schemas/project.py`
- Test: `tests_v2/contracts/test_project_schema_contract.py`

- [ ] **Step 1: Write the failing contract test**

Test exact field names for:

- `project_id`
- `name`
- `target.organization`
- `target.primary_person`
- `target.region`
- `analysis_period.start`
- `analysis_period.end`
- `comparison_period.start`
- `comparison_period.end`
- `channels`

Also verify extra fields are rejected.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests_v2/contracts/test_project_schema_contract.py -v`
Expected: FAIL because schemas do not exist yet.

- [ ] **Step 3: Implement common schemas**

Add:

- UUID aliases / shared config
- period schemas
- target schema
- versioned run schema

- [ ] **Step 4: Implement project schemas**

Add:

- `ProjectCreate`
- `ProjectRead`
- `ProjectWorkflowSnapshot`

Use Pydantic v2 with `extra="forbid"`.

- [ ] **Step 5: Run the test**

Run: `pytest tests_v2/contracts/test_project_schema_contract.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/schemas tests_v2/contracts/test_project_schema_contract.py
git commit -m "feat: add aiporg 2.0 project schemas"
```

## Task 4: Define Query, Collection, and Document Schemas

**Files:**
- Create: `app/schemas/query.py`
- Create: `app/schemas/collection.py`
- Create: `app/schemas/document.py`
- Test: `tests_v2/contracts/test_document_schema_contract.py`

- [ ] **Step 1: Write failing contract tests**

Verify exact shape for:

- `SearchQuery`
- `SearchResult`
- `RawDocument`
- `CleanDocument`
- `DuplicateClusterSchema`

Check required fields:

- `document_id`
- `channel`
- `platform`
- `source`
- `title`
- `body`
- `published_at`
- `url`
- `query`
- `metadata`
- `collected_at`

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests_v2/contracts/test_document_schema_contract.py -v`
Expected: FAIL

- [ ] **Step 3: Implement query and collection schemas**

Model:

- query text
- channel scoping
- run status
- run counts
- timestamps

- [ ] **Step 4: Implement document schemas**

Model:

- `SearchResult`
- `RawDocument`
- `CleanDocument`
- `DuplicateClusterSchema`

Use fixed field names from the PRD. Do not alias `published_at`.

- [ ] **Step 5: Run tests**

Run: `pytest tests_v2/contracts/test_document_schema_contract.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/schemas/query.py app/schemas/collection.py app/schemas/document.py tests_v2/contracts/test_document_schema_contract.py
git commit -m "feat: add aiporg 2.0 document contracts"
```

## Task 5: Define Evidence, Fact, Issue, Analytics, Narrative, Visualization, Report Schemas

**Files:**
- Create: `app/schemas/evidence.py`
- Create: `app/schemas/fact.py`
- Create: `app/schemas/issue.py`
- Create: `app/schemas/analytics.py`
- Create: `app/schemas/narrative.py`
- Create: `app/schemas/visualization.py`
- Create: `app/schemas/report.py`
- Test: `tests_v2/contracts/test_fact_schema_contract.py`
- Test: `tests_v2/contracts/test_issue_schema_contract.py`

- [ ] **Step 1: Write the failing contract tests**

Cover:

- `FactSchema.status`
- `FactSchema.source_count`
- `FactSchema.evidence_document_ids`
- `NumericFactSchema.confidence`
- `IssueCandidateSchema.document_count`
- `IssueSchema.subissues`
- `NarrativeContext`
- `ReportSchema`

Verify unsupported extra keys are rejected.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests_v2/contracts/test_fact_schema_contract.py tests_v2/contracts/test_issue_schema_contract.py -v`
Expected: FAIL

- [ ] **Step 3: Implement downstream schemas**

Use the PRD values exactly:

- fact statuses: `VERIFIED`, `SUPPORTED`, `UNCERTAIN`, `REJECTED`
- confidence grades: `A`, `B`, `C`, `D`
- subissue cap not enforced in schema logic yet, but list field must exist

- [ ] **Step 4: Run tests**

Run: `pytest tests_v2/contracts/test_fact_schema_contract.py tests_v2/contracts/test_issue_schema_contract.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/evidence.py app/schemas/fact.py app/schemas/issue.py app/schemas/analytics.py app/schemas/narrative.py app/schemas/visualization.py app/schemas/report.py tests_v2/contracts/test_fact_schema_contract.py tests_v2/contracts/test_issue_schema_contract.py
git commit -m "feat: add aiporg 2.0 evidence and reporting schemas"
```

## Task 6: Build SQLAlchemy Base and Core Models

**Files:**
- Create: `app/models/__init__.py`
- Create: `app/models/base.py`
- Create: `app/models/project.py`
- Create: `app/models/collection.py`
- Create: `app/models/document.py`
- Create: `app/models/evidence.py`
- Create: `app/models/fact.py`
- Create: `app/models/issue.py`
- Create: `app/models/analytics.py`
- Create: `app/models/narrative.py`
- Create: `app/models/visualization.py`
- Create: `app/models/report.py`
- Test: `tests_v2/unit/test_sqlalchemy_metadata.py`

- [ ] **Step 1: Write failing metadata tests**

Test:

```python
def test_metadata_contains_required_tables(): ...
def test_documents_unique_constraint_uses_project_id_and_canonical_url(): ...
def test_enum_columns_exist_on_collection_runs_and_facts(): ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests_v2/unit/test_sqlalchemy_metadata.py -v`
Expected: FAIL

- [ ] **Step 3: Implement declarative base**

Include shared mixins:

- UUID primary key mixin
- timestamp mixin
- version/run metadata mixin where needed

- [ ] **Step 4: Implement tables**

At minimum:

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

- [ ] **Step 5: Run tests**

Run: `pytest tests_v2/unit/test_sqlalchemy_metadata.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/models tests_v2/unit/test_sqlalchemy_metadata.py
git commit -m "feat: add aiporg 2.0 sqlalchemy models"
```

## Task 7: Define Repository Protocols

**Files:**
- Create: `app/repositories/__init__.py`
- Create: `app/repositories/base.py`
- Create: `app/repositories/project.py`
- Create: `app/repositories/collection.py`
- Create: `app/repositories/document.py`
- Create: `app/repositories/evidence.py`
- Create: `app/repositories/fact.py`
- Create: `app/repositories/issue.py`
- Create: `app/repositories/analytics.py`
- Create: `app/repositories/narrative.py`
- Create: `app/repositories/visualization.py`
- Create: `app/repositories/report.py`
- Test: `tests_v2/unit/test_repository_protocols.py`

- [ ] **Step 1: Write failing protocol tests**

Test that repository protocols expose expected methods, for example:

```python
def test_project_repository_has_create_and_get(): ...
def test_document_repository_has_upsert_raw_and_get_by_canonical_url(): ...
def test_report_repository_has_create_and_get_latest(): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests_v2/unit/test_repository_protocols.py -v`
Expected: FAIL

- [ ] **Step 3: Implement base repository contract**

Define shared protocol or abstract base for session-scoped repositories.

- [ ] **Step 4: Implement domain repository protocols**

Each protocol should type against Pydantic schema inputs/outputs, not SQLAlchemy models.

- [ ] **Step 5: Run tests**

Run: `pytest tests_v2/unit/test_repository_protocols.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/repositories tests_v2/unit/test_repository_protocols.py
git commit -m "feat: add aiporg 2.0 repository contracts"
```

## Task 8: Add Alembic Baseline for 2.0

**Files:**
- Create: `alembic_v2.ini`
- Create: `alembic_v2/env.py`
- Create: `alembic_v2/script.py.mako`
- Create: `alembic_v2/versions/20260814_000001_initial_phase0.py`
- Test: `tests_v2/unit/test_sqlalchemy_metadata.py`

- [ ] **Step 1: Write or extend migration application test**

Add a test that imports the metadata and verifies all tables are represented in the Alembic baseline revision.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests_v2/unit/test_sqlalchemy_metadata.py -v`
Expected: FAIL because Alembic files do not exist.

- [ ] **Step 3: Implement Alembic environment**

Configure:

- target metadata from `app.models.base`
- separate config file from any 1.0 migration path
- offline and online migration entrypoints

- [ ] **Step 4: Write initial revision**

The revision should create all Phase 0 tables and constraints only. No seed data.

- [ ] **Step 5: Run tests**

Run: `pytest tests_v2/unit/test_sqlalchemy_metadata.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add alembic_v2.ini alembic_v2 tests_v2/unit/test_sqlalchemy_metadata.py
git commit -m "feat: add aiporg 2.0 alembic baseline"
```

## Task 9: Add Minimal Config and Logging Stubs

**Files:**
- Create: `app/core/config.py`
- Create: `app/core/logging.py`
- Test: none

- [ ] **Step 1: Implement config stub**

Add minimal settings object for:

- database URL
- environment
- log level

Do not add collector credentials yet.

- [ ] **Step 2: Implement logging stub**

Add a reusable logger factory for 2.0 modules.

- [ ] **Step 3: Smoke-check imports**

Run: `python -c "from app.core.config import Settings; from app.core.logging import get_logger"`
Expected: exits successfully.

- [ ] **Step 4: Commit**

```bash
git add app/core/config.py app/core/logging.py
git commit -m "chore: add aiporg 2.0 core config stubs"
```

## Task 10: Run Phase 0 Verification

**Files:**
- Modify: none
- Test: `tests_v2/contracts/*.py`
- Test: `tests_v2/unit/*.py`

- [ ] **Step 1: Run contract tests**

Run: `pytest tests_v2/contracts -v`
Expected: PASS

- [ ] **Step 2: Run unit tests**

Run: `pytest tests_v2/unit -v`
Expected: PASS

- [ ] **Step 3: Run full 2.0 test slice**

Run: `pytest tests_v2 -v`
Expected: PASS

- [ ] **Step 4: Run mypy for 2.0 package**

Run: `mypy app`
Expected: no type errors for the new package.

- [ ] **Step 5: Show dependency diagram artifact**

Create a short markdown summary in:

`docs/aiporg2/phase0-dependency-diagram.md`

with:

```text
schemas -> repositories -> services (future)
schemas -> models (mapping boundary only)
state_machine -> services (future)
alembic -> models
tests -> schemas/models/repositories/state_machine
```

- [ ] **Step 6: Commit**

```bash
git add docs/aiporg2/phase0-dependency-diagram.md
git commit -m "test: verify aiporg 2.0 phase 0 baseline"
```

## Notes for the Implementer

- Do not modify `aiporg/`, `tests/`, or existing 1.0 CLI paths.
- Do not add collectors, HTTP clients, or LLM providers in this phase.
- Keep all schema field names exactly aligned with the PRD.
- If a required detail is ambiguous, document it instead of inventing behavior.
