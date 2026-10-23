# IssueScope Research & Analysis Engine Design

## Goal

Evolve the existing AIPORG 2.0 branch into a reusable issue-driven research and opinion analysis engine. A project receives a general target, an analysis period, and user-selected issues. The engine researches those issues, traces claims to evidence, analyzes public reactions, and prepares a reviewable report.

## Current foundation

The branch starts from the existing 2.0 application: Streamlit, SQLite/SQLAlchemy repositories, channel collectors, article extraction, Evidence/Fact workflows, analytics, narrative review, visualization approval, and a report prototype. The existing `Issue` means an evidence-backed analytical grouping; it must not silently be repurposed to mean a user-entered research issue.

## Proposed design

- Keep the cleanup/design checkpoint in `feat/issuescope-research-engine` and start feature work in `feat/issuescope-implementation` from that commit; the original worktree and its uncommitted changes remain untouched.
- Use `Project.target.region`, `Project.analysis_period`, and explicit user issue records as the project inputs. Keep organization/person fields optional in the UI while preserving the existing Pydantic model names.
- Add a distinct `ResearchIssue` persistence concept for user-defined issues. Link every generated `Query` to exactly one research issue and retain its query purpose (FACT, DETAIL, IMPACT, CONCERN, REACTION). Existing `Issue` and `IssueSchema` keep their current meaning and names.
- Add a `ResearchWorkflow` orchestration layer. It may use the Narrative LLM adapter to plan queries and identify missing information, but it delegates all network access to existing Collectors and keeps deterministic analysis free of web requests. A collector never calls an LLM.
- Reuse `Document → Evidence → Fact` and existing repositories for source lineage. A claim or number shown in analysis must cite stored evidence. Conflicting facts remain visible as conflicts; the writer may summarize only supplied, cited facts.
- Bound research with explicit iteration, query, and source budgets. Do not add workflow enum states until a separate state-machine design proves they are needed.
- Keep Streamlit as the user interface. Do not introduce FastAPI, PostgreSQL, a queue service, vector database, or automatic issue discovery in this project.
- Separate verified factual research from public reaction in analysis outputs. Reuse existing channel and sentiment primitives first; add aspect/frame/reason persistence only after their contracts are specified.

## First implementation milestone

Persist user-selected research issues, generate purpose-tagged searches linked to those issues, and show the issue-to-query relationship in the existing Streamlit flow. This establishes the core input contract without attempting the full research loop in one change.

## Constraints and risks

The issue/query relationship requires a schema migration and new named contracts; this is an explicit PRD-backed design decision, not an incidental schema addition. Existing Pydantic names remain stable. The current one-way project workflow cannot be re-entered for a follow-up search, so the iterative loop needs an orchestrator that respects existing collection run and repository semantics. Search coverage, provider quotas, and article access vary; `COMPLETE` must not imply comprehensive coverage of the public internet.

## Acceptance direction

For one user-defined issue, the app can persist its identity, associate one or more purpose-tagged queries, collect results through existing collectors, and retain evidence provenance. Later slices add bounded follow-up research, reaction analysis, cross-issue synthesis, and same-version report export.
