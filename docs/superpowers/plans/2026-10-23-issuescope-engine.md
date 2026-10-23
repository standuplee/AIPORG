# IssueScope Research & Analysis Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing AIPORG 2.0 application on `feat/issuescope-implementation` into a general issue-driven research and opinion analysis engine while leaving the original working branch untouched.

**Architecture:** Keep the existing Streamlit, Repository, Collector, Evidence, Fact, Analytics, Narrative, and Report layers. Add a user-defined ResearchIssue domain that is distinct from the existing evidence-derived Issue, then introduce a coordinator that plans bounded queries through the Narrative adapter and delegates web access to Collectors.

**Tech Stack:** Python 3.12, Streamlit, Pydantic, SQLAlchemy, Alembic, existing SQLite persistence and provider adapters.

---

## File map

- `app/models/` and `app/schemas/`: add the explicit user research-issue contract without renaming existing models.
- `app/repositories/` and `app/repositories/sqlalchemy.py`: persist and retrieve research issues and their query associations.
- `alembic_v2/versions/`: add only the migration required by the approved issue/query contract.
- `app/research/`: query planning, bounded research orchestration, and completeness decisions; no direct database writes or direct web calls.
- `app/workflows/`: connect orchestration to existing collection/evidence workflows without re-entering one-way states.
- `streamlit_app/console.py`: accept region/period/issues and display per-issue progress and query links.
- `tests_v2/unit/`, `tests_v2/contracts/`, `tests_v2/integration/`: cover contract validation, repositories, query planning, and persisted end-to-end lineage.
- `README.md`, `HANDOFF.md`: describe IssueScope on this branch and preserve the older AIPORG context on its original branch.

## Task 1: Persist user-defined research issues

**Files:**
- Create: `app/models/research_issue.py`
- Create: `app/schemas/research_issue.py`
- Modify: `app/models/project.py` and `app/models/__init__.py`
- Modify: `app/repositories/` and `app/repositories/sqlalchemy.py`
- Modify: `streamlit_app/console.py` to capture user-defined research issues during project setup
- Create: `alembic_v2/versions/<timestamp>_add_research_issues.py`
- Test: `tests_v2/unit/test_research_issue_contract.py`
- Test: `tests_v2/unit/test_sqlalchemy_repositories.py`
- Test: `tests_v2/integration/test_research_issue_persistence.py`
- Test: `tests_v2/integration/test_research_issue_migration.py`
- Test: `tests_v2/unit/test_research_issue_ui.py`

- [ ] Define and validate the user issue contract, including non-empty label and stable project-scoped identity.
- [ ] Register the model in `app/models/__init__.py`; persist user issues through a Repository.
- [ ] Add a migration with foreign keys and project-scoped uniqueness; test upgrading a pre-migration database with existing projects, queries, and collection runs.
- [ ] Update the project setup UI to create the user issue records; test the focused form/serialization behavior.
- [ ] Add focused unit, contract, and integration coverage.
- [ ] Run the integration slice before starting the next feature, per repository rules.

## Task 2: Generate a bounded Research Plan

**Files:**
- Create: `app/research/planner.py`
- Create: `app/schemas/research_plan.py`
- Modify: `app/schemas/query.py`, `app/models/project.py`, `app/repositories/collection.py`, and `app/repositories/sqlalchemy.py` to link queries to one research issue and purpose
- Create: `alembic_v2/versions/<timestamp>_add_issue_query_link.py` with nullable fields for compatibility
- Modify: `streamlit_app/console.py` to generate and display each issue's purpose-tagged query plan
- Test: `tests_v2/unit/test_research_issue_ui.py`
- Modify: existing Narrative adapter only if needed to expose structured JSON safely
- Test: `tests_v2/unit/test_research_planner.py`
- Test: `tests_v2/unit/test_sqlalchemy_repositories.py` for issue-linked append-only queries
- Test: `tests_v2/integration/test_issue_query_migration.py` preserving existing queries and collection-run foreign keys

- [ ] Generate purpose-tagged FACT, DETAIL, IMPACT, CONCERN, and REACTION queries from one user issue and project target.
- [ ] Extend `SearchQuery` with an optional project-scoped research issue ID and purpose so pre-existing project-wide queries remain readable.
- [ ] Add append-only query persistence for generated and follow-up searches; retain old query rows referenced by collection runs.
- [ ] Show persisted generated queries by their user issue in Streamlit.
- [ ] Validate query count, length, and allowed query purposes at the boundary.
- [ ] Keep the planner outside all Collector implementations; persist outputs through repositories.
- [ ] Test provider success, malformed output, missing API key, and deterministic fallback behavior.

## Task 3: Run bounded collection and follow-up research

**Files:**
- Create: `app/research/workflow.py`
- Reuse: `app/collection/service.py`, `app/cleaning/service.py`, `app/dedup/service.py`, `app/evidence/service.py`, and `app/facts/extraction.py`
- Modify: `app/workflows/multi_query_collection_to_evidence.py` only if its existing one-shot behavior remains unchanged
- Test: `tests_v2/unit/test_research_workflow.py`
- Test: `tests_v2/integration/test_research_workflow.py`

- [ ] Advance project collection state once. For each round, call the existing `CollectionService` directly for newly persisted queries; do not re-enter the one-shot workflow or replace prior queries.
- [ ] Between rounds, build an in-memory preview from all raw collection-run documents: clean, deduplicate, create deterministic Evidence values, and extract preview Facts. Use preview data only for planning; persist the final canonical documents, Evidence, and Facts once after research stops.
- [ ] Define a fixed `ResearchDimension` contract from the PRD checklist (background, date, content, actors, numeric details, target role, effects, concerns, future plan, trusted sources). Map dimensions only to existing evidence-backed Fact IDs. If the LLM cannot support a mapping, leave it unfilled.
- [ ] Detect missing dimensions and enqueue purpose-tagged follow-up queries, with configured iteration/query/source budgets.
- [ ] Stop when no supported missing dimensions remain or a budget is reached; report incomplete when a budget ends with dimensions still missing.
- [ ] Add an integration test proving two collection rounds can complete on one project without state re-entry or loss of first-round collection runs/evidence.
- [ ] Preserve collection failures and incomplete status without inventing facts or numeric values.

## Task 4: Separate factual research from public reaction

**Files:**
- Modify: existing analytics/sentiment services only after reviewing their callers
- Create: a focused reaction analysis service only if existing services cannot represent the required result
- Test: focused unit and integration tests

- [ ] Exclude unsupported claims and clearly distinguish factual evidence from public reaction.
- [ ] Report YouTube and other channel counts from observed persisted documents, with comments separate from video/article mentions.
- [ ] Add target/frame/reason classifications only with an explicit contract and evidence-linked inputs.

## Task 5: Synthesize and export reviewed reports

**Files:**
- Modify: `app/narrative/`, `app/report/`, and `streamlit_app/console.py`
- Modify: `app/models/report.py`, `app/schemas/report.py`, `app/repositories/report.py`, `app/repositories/sqlalchemy.py`, `app/models/__init__.py`, and `alembic_v2/versions/` to persist exact approved narrative/visualization version references
- Create: Alembic upgrade integration test preserving existing reports
- Create or modify: unit/integration tests for synthesis and output approval lineage

- [ ] Synthesize issue results across the project from cited facts and observed reactions.
- [ ] Keep the existing human review/approval gate before export.
- [ ] Pin the exact approved narrative and visualization version identifiers in the Report record; test migration and output after a later edit.
- [ ] Add Markdown/HTML/DOCX only by reusing existing writers where possible; keep HWPX work in its existing writer.

## Task 6: Documentation and cleanup

**Files:**
- Modify: `README.md`, `HANDOFF.md`
- Remove: only obsolete generated outputs and unused legacy API files/dependencies already identified

- [ ] Document IssueScope inputs, limits, and local execution.
- [ ] Keep the original branch's dirty changes isolated; do not merge or push without a completed feature review.
- [ ] Run the requested focused test suites and report any remaining external/manual checks.
