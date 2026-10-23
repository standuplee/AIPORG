"""AIPORG 2.0 Streamlit console (M4 minimal unit).

Scope decided 2026-10-16: no fixed base search terms, the monthly keyword
list typed here is the entire search scope; comments are collected (see
``docs/aiporg2/narrative-design.md`` and the implementation plan for the
``metadata["document_type"]`` convention, not wired into collectors yet);
LLM drafting is an API-based adapter with the key supplied later; X and
Instagram are out of scope (paid access), Google is in scope but has no
collector implemented yet.

This page only wires together existing ``app/`` contracts (repositories,
collection service, enums, plus the additive output/approval contracts in
``docs/aiporg2/visualization-design.md``, 2026-10-18). Narrative drafting,
visualization (VIS-02 channel donut + VIS-07 TOP10 cards only -- the rest of
VIS-01..09 are not built yet), and final report approval are implemented and
wired end to end. "8. 출력·이력" only offers a 3-page HWPX prototype (cover,
TOC, summary) once a report is approved -- full DOCX/Markdown writers and the
real 12-page HWPX assembly are not implemented yet (M5/M6 sections of
``docs/superpowers/plans/2026-09-08-aiporg2-implementation.md``). The HWPX
prototype has not been opened in real Hancom Office from this environment --
that verification still needs a human with the actual editor.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

# ``streamlit run streamlit_app/console.py`` puts this file's own directory on
# sys.path, not the invoking shell's cwd or the repo root, so the top-level
# ``app`` package is not importable unless we add the repo root ourselves.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Nothing in app/core/config.py reads a .env file -- Settings.from_env() only
# reads already-exported process environment variables. Load the repo's .env
# here, before anything calls get_settings() (which is lru_cache'd, so this
# must happen before its first call in this process). This does not override
# variables the shell already exported.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import analytics_ui

from app.cleaning.service import CleaningService
from app.collectors.community import CommunityCollector, load_policies as load_community_policies
from app.collectors.daum_news import DaumNewsCollector
from app.collectors.naver_news import NaverNewsCollector
from app.collectors.google_search import GoogleSearchCollector
from app.collectors.youtube import YouTubeCollector
from app.core.config import Settings, get_settings
from app.core.enums import (
    ChannelType,
    CollectionRunStatus,
    FactStatus,
    SentimentLabel,
    WorkflowState,
)
from app.core.state_machine import InvalidStateTransitionError
from app.db.session import create_session_factory, session_scope
from app.dedup.service import DeduplicationService
from app.evidence.service import EvidenceService
from app.facts.extraction import FactExtractionService
from app.facts.validation import FactValidationService
from app.issues.discovery import IssueDiscoveryService
from app.issues.finalization import IssueFinalizationService
from app.models.project import Query
from app.narrative.llm_adapter import GeminiNarrativeAdapter, NarrativeGenerationError
from app.narrative.reasons import (
    aggregate_issue_sentiment,
    derive_narrative_reasons,
    render_star_rating,
    sentiment_to_stars,
    summarize_subissue_sentiment_counts,
)
from app.narrative.template import TemplateNarrativeService
from app.report.approval import ReportApprovalError, ReportApprovalService
from app.report.hwpx_writer import HwpxPrototypeError, build_cover_toc_summary
from app.repositories.sqlalchemy import (
    SqlAlchemyAnalyticsRepository,
    SqlAlchemyCollectionRunRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyDuplicateClusterRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyFactRepository,
    SqlAlchemyIssueRepository,
    SqlAlchemyNarrativeRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyQuerySetRepository,
    SqlAlchemyReportRepository,
    SqlAlchemyVisualizationRepository,
)
from app.schemas.common import (
    AnalysisPeriodSchema,
    ComparisonPeriodSchema,
    TargetSchema,
    VersionedRunSchema,
)
from app.schemas.narrative import (
    NarrativeContext,
    NarrativeOutputSchema,
    NarrativeSentenceSchema,
)
from app.schemas.project import ProjectCreate
from app.schemas.query import SearchQuery
from app.schemas.visualization import VisualizationOutputSchema
from app.visualization.service import (
    CHANNEL_DONUT_SLOT,
    TOP10_KEYWORDS_SLOT,
    VisualizationRenderError,
    VisualizationRenderService,
)
from app.workflows.evidence_to_issues import EvidenceToIssuesWorkflow
from app.workflows.multi_query_collection_to_evidence import (
    CollectionRequest,
    MultiQueryCollectionToEvidenceWorkflow,
)

VISUALIZATION_SLOTS = {
    CHANNEL_DONUT_SLOT: "채널 비중 도넛 (VIS-02)",
    TOP10_KEYWORDS_SLOT: "TOP10 키워드 카드 (VIS-07)",
}

# label -> settings credential key used to build the real collector.
IMPLEMENTED_PROVIDERS = ["naver", "daum", "youtube", "google", "community"]
PROVIDER_LABELS = {
    "naver": "네이버 뉴스",
    "daum": "다음 뉴스",
    "youtube": "유튜브",
    "google": "구글 검색",
    "community": "커뮤니티 (클리앙/디시인사이드/펨코/루리웹/더쿠)",
}
PROVIDER_CHANNELS = {
    "naver": ChannelType.NEWS,
    "daum": ChannelType.NEWS,
    "youtube": ChannelType.VIDEO,
    # Google is a discovery path across content types, not one channel --
    # tagged NEWS as a documented simplification (see
    # app/collectors/google_search.py's module docstring).
    "google": ChannelType.NEWS,
    "community": ChannelType.COMMUNITY,
}

# app/core/state_machine.py enforces this exact forward-only order; mirrored
# here only to answer "is this project at least at stage X" for UI gating.
_WORKFLOW_STATE_ORDER = [
    WorkflowState.CREATED,
    WorkflowState.QUERIES_READY,
    WorkflowState.COLLECTION_RUNNING,
    WorkflowState.COLLECTION_COMPLETED,
    WorkflowState.CLEANING_COMPLETED,
    WorkflowState.EVIDENCE_COMPLETED,
    WorkflowState.ISSUES_COMPLETED,
    WorkflowState.ANALYTICS_COMPLETED,
    WorkflowState.NARRATIVE_COMPLETED,
    WorkflowState.VISUALS_COMPLETED,
    WorkflowState.REPORT_COMPLETED,
]


def _state_at_least(current: WorkflowState, target: WorkflowState) -> bool:
    return _WORKFLOW_STATE_ORDER.index(current) >= _WORKFLOW_STATE_ORDER.index(target)


@st.cache_resource
def get_session_factory() -> sessionmaker:
    """Apply Alembic migrations once per process, then hand back a session factory.

    ``alembic upgrade head`` is idempotent, so running it on every app start
    is safe and keeps ``streamlit run`` a single command with no separate
    migration step.
    """

    from alembic import command
    from alembic.config import Config

    settings = get_settings()
    config = Config(str(REPO_ROOT / "alembic_v2.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic_v2"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
    return create_session_factory(settings.database_url)


def build_collectors(settings: Settings) -> dict[str, object]:
    collectors: dict[str, object] = {}
    if settings.naver_client_id and settings.naver_client_secret:
        collectors["naver"] = NaverNewsCollector(
            client_id=settings.naver_client_id,
            client_secret=settings.naver_client_secret,
        )
    if settings.kakao_rest_api_key:
        collectors["daum"] = DaumNewsCollector(api_key=settings.kakao_rest_api_key)
    if settings.youtube_api_key:
        collectors["youtube"] = YouTubeCollector(api_key=settings.youtube_api_key)
    if settings.google_api_key and settings.google_search_engine_id:
        collectors["google"] = GoogleSearchCollector(
            api_key=settings.google_api_key,
            search_engine_id=settings.google_search_engine_id,
        )
    if settings.naver_client_id and settings.naver_client_secret:
        # Discovery reuses the Naver web-search API, same credentials as the
        # news collector -- no separate community API key exists for any of
        # the five sites. Collection still yields nothing until an operator
        # enables at least one site in config/community.yaml (see the
        # caption next to the checkbox in page_collect()).
        collectors["community"] = CommunityCollector(
            client_id=settings.naver_client_id,
            client_secret=settings.naver_client_secret,
        )
    return collectors


def _default_comparison_period(start: date, end: date) -> ComparisonPeriodSchema:
    span_days = (end - start).days
    from datetime import timedelta

    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=span_days)
    return ComparisonPeriodSchema(start=previous_start, end=previous_end)


def _require_active_project() -> str | None:
    project_id = st.session_state.get("active_project_id")
    if not project_id:
        st.warning("먼저 '1. 월별 프로젝트' 화면에서 프로젝트를 만들거나 선택하세요.")
        return None
    st.caption(f"활성 프로젝트: `{project_id}`")
    return project_id


def page_project(factory: sessionmaker) -> None:
    st.header("1. 월별 프로젝트")
    st.caption(
        "조사 기간과 맥락 정보(기관/인물/지역)만 여기서 정하며, 검색어에 자동으로 "
        "합치지 않는다. 실제 조사 범위는 '2. 수집 설정·실행'에서 입력한 키워드 "
        "리스트 전체다."
    )

    with st.form("create_project"):
        name = st.text_input("프로젝트 이름", placeholder="충남 2026-09")
        col1, col2, col3 = st.columns(3)
        organization = col1.text_input("기관(맥락)", value="충청남도")
        primary_person = col2.text_input("주요 인물(맥락)", value="도지사")
        region = col3.text_input("지역(맥락)", value="충남")
        col4, col5 = st.columns(2)
        start = col4.date_input("조사 시작일", value=date.today().replace(day=1))
        end = col5.date_input("조사 종료일", value=date.today())
        submitted = st.form_submit_button("프로젝트 생성")

    if submitted:
        if not name.strip():
            st.error("프로젝트 이름을 입력하세요.")
        elif start > end:
            st.error("시작일은 종료일보다 앞서야 합니다.")
        else:
            with session_scope(factory) as session:
                project = SqlAlchemyProjectRepository(session).create(
                    ProjectCreate(
                        name=name,
                        target=TargetSchema(
                            organization=organization,
                            primary_person=primary_person,
                            region=region,
                        ),
                        analysis_period=AnalysisPeriodSchema(start=start, end=end),
                        comparison_period=_default_comparison_period(start, end),
                        channels=[ChannelType.NEWS],
                    )
                )
            st.session_state["active_project_id"] = str(project.project_id)
            st.success(f"프로젝트 생성됨: {project.project_id}")
            st.rerun()

    st.subheader("저장된 프로젝트")
    st.caption("DB에 저장된 전체 프로젝트 목록이다 — 앱을 재시작해도 남는다.")
    with session_scope(factory) as session:
        project_repository = SqlAlchemyProjectRepository(session)
        projects = project_repository.list()
        workflow_states = {
            item.project_id: project_repository.get_workflow(item.project_id).workflow_state
            for item in projects
        }
    if projects:
        for item in projects:
            selected = str(item.project_id) == st.session_state.get("active_project_id")
            state = workflow_states[item.project_id].value
            label = (
                f"{'➡️ ' if selected else ''}{item.name} "
                f"({item.analysis_period.start} ~ {item.analysis_period.end}) "
                f"[{state}] — `{item.project_id}`"
            )
            if st.button(label, key=f"select-{item.project_id}"):
                st.session_state["active_project_id"] = str(item.project_id)
                st.rerun()
    else:
        st.info("아직 생성한 프로젝트가 없다.")


def page_collect(factory: sessionmaker) -> None:
    st.header("2. 수집 설정·실행")
    project_id_str = _require_active_project()
    if project_id_str is None:
        return
    project_id = UUID(project_id_str)

    with session_scope(factory) as session:
        project_repository = SqlAlchemyProjectRepository(session)
        project = project_repository.get(project_id)
        workflow = project_repository.get_workflow(project_id)
    if workflow is None or project is None:
        st.error("프로젝트를 찾지 못했다.")
        return
    if workflow.workflow_state not in {WorkflowState.CREATED, WorkflowState.QUERIES_READY}:
        st.warning(
            f"이 프로젝트는 이미 수집을 실행했다(현재 상태: `{workflow.workflow_state.value}`). "
            "프로젝트의 workflow state는 한 번만 전진하는 구조라 같은 프로젝트에서 수집을 "
            "다시 실행할 수 없다. 키워드를 바꿔 다시 수집하려면 '1. 월별 프로젝트'에서 새 "
            "프로젝트를 만들어라."
        )
        with session_scope(factory) as session:
            queries = SqlAlchemyQuerySetRepository(session).get(project_id)
        st.markdown(f"**조사 기간:** {project.analysis_period.start} ~ {project.analysis_period.end}")
        if queries:
            st.markdown(f"**수집한 키워드 ({len(queries)}개):**")
            st.markdown("\n".join(f"- {query.query}" for query in queries))
        else:
            st.caption("저장된 키워드를 찾지 못했다.")
        st.caption(
            "조사 기간은 '1. 월별 프로젝트'에서 설정한 값이다 — naver/daum 등 "
            "collector가 아직 날짜로 결과를 거르지 않으므로(위 6차 기록 참고), "
            "실제로 수집된 문서가 이 기간 안에만 있다는 보장은 아니다. '3. 수집 "
            "결과 검토'에서 실행 이력과 실제 문서 수를 확인하라."
        )
        return

    settings = get_settings()
    collectors = build_collectors(settings)

    with st.form("collect_form"):
        col1, col2 = st.columns(2)
        start = col1.date_input("수집 기간 시작", value=project.analysis_period.start)
        end = col2.date_input("수집 기간 종료", value=project.analysis_period.end)
        st.caption(
            f"기본값은 '1. 월별 프로젝트'에서 설정한 조사 기간"
            f"({project.analysis_period.start} ~ {project.analysis_period.end})이다. "
            "필요하면 여기서 바꿀 수 있다. 다만 naver/daum collector는 아직 날짜로 "
            "결과를 거르지 않는다 — 이 기간은 지금은 안내용이고, 실제 수집 결과를 "
            "기간으로 제한하는 기능은 아직 구현 전이다(요구사항 §3.1 참고)."
        )
        keywords_raw = st.text_area(
            "핵심 키워드 (한 줄에 하나, 개수 제한 없음)",
            height=180,
            placeholder=(
                "공공기관 충남 2차 이전, 내포신도시\n"
                "충남 재정전략회의\n"
                "인사청문특위 부적격판단 전격수용\n"
                "삼성 디스플레이 67조 투자유치"
            ),
        )
        st.caption(
            "기본 조사어(지역/기관/인물)는 자동으로 추가되지 않는다. "
            "위에 입력한 줄 전체가 이번 수집의 검색어다. 한 줄에 여러 단어를 "
            "써도 AIPORG가 '모든 단어 포함'을 강제하지 않는다 — 각 줄 전체를 "
            "그대로 검색 API에 전달하고(네이버·다음은 query, 구글·유튜브는 q), "
            "단어가 실제로 다 포함되는지는 각 검색엔진의 토큰화·유사어 처리에 "
            "달려 있다."
        )

        st.markdown("**실행할 채널**")
        selected_providers: list[str] = []
        for provider_key in IMPLEMENTED_PROVIDERS:
            available = provider_key in collectors
            label = PROVIDER_LABELS[provider_key]
            status = "✅ 구현됨" if available else "⚠️ 자격증명 없음 (.env의 AIPORG2_* 값 필요)"
            checked = st.checkbox(f"{label} — {status}", value=available, disabled=not available)
            if checked and available:
                selected_providers.append(provider_key)
        if "community" in collectors:
            enabled_sites = sorted(
                name for name, policy in load_community_policies().items() if policy.enabled
            )
            if enabled_sites:
                st.caption(f"커뮤니티 활성 사이트: {', '.join(enabled_sites)}")
            else:
                st.caption(
                    "커뮤니티는 `config/community.yaml`의 모든 사이트가 기본 "
                    "`enabled: false`다(운영자가 각 사이트의 robots.txt·이용약관을 "
                    "검토한 뒤 직접 활성화해야 한다, 1.0부터 유지된 안전장치). 지금 "
                    "체크해도 활성 사이트가 없으면 결과 0건으로 끝난다 — 오류가 "
                    "아니다."
                )

        submitted = st.form_submit_button("수집 실행")

    if not submitted:
        return

    keywords = [line.strip() for line in keywords_raw.splitlines() if line.strip()]
    if start > end:
        st.error("시작일은 종료일보다 앞서야 한다.")
        return
    if not keywords:
        st.error("키워드를 한 줄에 하나씩 입력하라.")
        return
    if not selected_providers:
        st.error("실행 가능한 채널을 하나 이상 선택하라.")
        return

    _run_collection(factory, project_id, keywords, selected_providers, collectors)


def _run_collection(
    factory: sessionmaker,
    project_id: UUID,
    keywords: list[str],
    selected_providers: list[str],
    collectors: dict[str, object],
) -> None:
    requested_channels = sorted(
        {PROVIDER_CHANNELS[provider_key] for provider_key in selected_providers},
        key=lambda channel: channel.value,
    )
    queries = [
        SearchQuery(query=keyword, channels=requested_channels) for keyword in keywords
    ]

    status_line = st.empty()
    status_line.write(
        f"{len(keywords)}개 키워드 × {len(selected_providers)}개 채널 수집 중 "
        "(완료까지 결과가 보이지 않을 수 있다 — 네트워크 호출 포함)..."
    )

    with session_scope(factory) as session:
        SqlAlchemyQuerySetRepository(session).create(project_id, queries)
        project_repository = SqlAlchemyProjectRepository(session)
        snapshot = project_repository.get_workflow(project_id)
        if snapshot is not None and snapshot.workflow_state is WorkflowState.CREATED:
            project_repository.advance_workflow(project_id, WorkflowState.QUERIES_READY)
        query_rows = session.execute(
            select(Query.id, Query.query).where(Query.project_id == project_id)
        ).all()
        query_id_by_text = {text: query_id for query_id, text in query_rows}

        requests = [
            CollectionRequest(
                collector=collectors[provider_key],
                query_id=query_id_by_text[keyword],
                run_id=uuid4(),
                query=SearchQuery(
                    query=keyword, channels=[PROVIDER_CHANNELS[provider_key]]
                ),
            )
            for keyword in keywords
            if keyword in query_id_by_text
            for provider_key in selected_providers
        ]
        missing = [keyword for keyword in keywords if keyword not in query_id_by_text]
        for keyword in missing:
            st.warning(f"'{keyword}'에 대한 query_id를 찾지 못해 건너뜀.")

        workflow = MultiQueryCollectionToEvidenceWorkflow(
            collection_run_repository=SqlAlchemyCollectionRunRepository(session),
            cleaning_service=CleaningService(),
            deduplication_service=DeduplicationService(),
            evidence_service=EvidenceService(),
            project_repository=SqlAlchemyProjectRepository(session),
            document_repository=SqlAlchemyDocumentRepository(session),
            duplicate_cluster_repository=SqlAlchemyDuplicateClusterRepository(session),
            evidence_repository=SqlAlchemyEvidenceRepository(session),
        )
        try:
            results = asyncio.run(workflow.run(project_id=project_id, requests=requests))
        except (ValueError, InvalidStateTransitionError) as exc:
            status_line.write("")
            st.error(f"수집을 시작할 수 없다: {exc}")
            return

    failed = [r for r in results if r.status is CollectionRunStatus.FAILED]
    completed = [r for r in results if r.status is CollectionRunStatus.COMPLETED]
    status_line.write(
        f"수집 완료: {len(completed)}개 실행 성공, {len(failed)}개 실패. "
        "정제·중복 제거·Evidence까지 자동으로 연결됐다. "
        "'3. 수집 결과 검토'에서 진행 상황과 건수를, "
        "'4. 통계·이슈 검토'에서 Evidence 결과를 확인하라."
    )
    if failed:
        st.warning(f"{len(failed)}개 실행이 실패했다 — 아래 '3. 수집 결과 검토'에서 상세 확인.")


def page_progress(factory: sessionmaker) -> None:
    st.header("3. 수집 결과 검토·진행 상황")
    project_id_str = _require_active_project()
    if project_id_str is None:
        return
    project_id = UUID(project_id_str)

    st.caption("DB에 저장된 이 프로젝트의 전체 수집 실행 이력이다 — 앱을 재시작해도 남는다.")
    st.button("새로고침")

    with session_scope(factory) as session:
        runs = SqlAlchemyCollectionRunRepository(session).list_by_project(project_id)
        document_repository = SqlAlchemyDocumentRepository(session)
        rows = [
            {
                "키워드": run.query,
                "채널": run.channel.value,
                "상태": run.status.value,
                "발견": run.documents_found,
                "저장": run.documents_saved,
                "오류": run.error_count,
                "시작": run.started_at.isoformat(),
            }
            for run in runs
        ]
        source_counts: dict[str, int] = {}
        for run in runs:
            if run.status is not CollectionRunStatus.COMPLETED:
                continue
            for document in document_repository.list_raw_by_collection_run(project_id, run.id):
                source_counts[document.source] = source_counts.get(document.source, 0) + 1

    if not rows:
        st.info("아직 실행한 수집 작업이 없다. '2. 수집 설정·실행'에서 먼저 실행하라.")
        return

    st.subheader("키워드 × 채널별 진행 상황")
    st.dataframe(rows, use_container_width=True)

    st.subheader("출처(사이트)별 확보 건수 (대략치)")
    if source_counts:
        st.bar_chart(source_counts)
    else:
        st.info("완료된 수집 건이 아직 없다.")


def page_analytics(factory: sessionmaker) -> None:
    st.header("4. 통계·이슈 검토")
    project_id_str = _require_active_project()
    if project_id_str is None:
        return
    project_id = UUID(project_id_str)

    st.caption(
        "정제·중복 제거·Evidence까지는 '2. 수집 설정·실행'에서 자동으로 연결된다. "
        "이슈 확정과 통계 집계는 아래 버튼으로 이 화면에서 바로 실행한다. 감성 "
        "분류는 기존 metadata 라벨 집계뿐이고 연관 키워드는 형태소 분석이 아닌 "
        "문자 토큰 빈도다(docs/aiporg2/analytics.md 참고) — 보여주는 수치의 산식 "
        "자체는 M2에서 더 보완해야 한다. 댓글(유튜브·네이버)은 `comment_count`로 "
        "따로 집계되고 본문 언급량(`unique_documents`)에는 섞이지 않는다."
    )

    with session_scope(factory) as session:
        project_repository = SqlAlchemyProjectRepository(session)
        workflow = project_repository.get_workflow(project_id)
        document_count = SqlAlchemyDocumentRepository(session).count_canonical(project_id)
        evidence_count = SqlAlchemyEvidenceRepository(session).count_by_project(project_id)
    if workflow is None:
        st.error("프로젝트를 찾지 못했다.")
        return

    col1, col2 = st.columns(2)
    col1.metric("고유(canonical) 문서 수", document_count)
    col2.metric("Evidence 수", evidence_count)
    st.caption(f"현재 workflow 상태: `{workflow.workflow_state.value}`")

    if document_count == 0:
        st.info("아직 Evidence까지 도달한 문서가 없다. 먼저 수집을 실행하라.")
        return

    st.subheader("고유 문서 목록")
    page_size = 50
    page_key = f"analytics-doc-page-{project_id}"
    page = st.session_state.get(page_key, 0)
    max_page = max((document_count - 1) // page_size, 0)
    page = min(page, max_page)
    with session_scope(factory) as session:
        document_rows = SqlAlchemyDocumentRepository(session).list_canonical_page(
            project_id, limit=page_size, offset=page * page_size,
        )
    analytics_ui.render_document_page(
        document_rows, offset=page * page_size, page_size=page_size, total=document_count,
    )
    nav_prev, nav_next = st.columns(2)
    if nav_prev.button("이전 페이지", disabled=page <= 0, key=f"{page_key}-prev"):
        st.session_state[page_key] = page - 1
        st.rerun()
    if nav_next.button("다음 페이지", disabled=page >= max_page, key=f"{page_key}-next"):
        st.session_state[page_key] = page + 1
        st.rerun()

    st.divider()
    st.subheader("이슈 확정")
    current = workflow.workflow_state
    if current is WorkflowState.EVIDENCE_COMPLETED:
        st.caption(
            "Evidence에서 결정론적으로 fact를 추출하고(`app/facts/extraction.py`), "
            "VERIFIED/SUPPORTED 여부를 검증한 뒤(`app/facts/validation.py`) 이슈로 "
            "묶는다(`app/issues/discovery.py`, `finalization.py`). 공식 출처 목록을 "
            "설정하는 UI가 아직 없어 전부 '비공식 출처'로 판정한다(복수 독립 출처 "
            "조건으로만 검증 통과 가능) — 공식 출처 정책은 추후 결정 대상."
        )
        if st.button("이슈 확정 실행"):
            with session_scope(factory) as session:
                issues_workflow = EvidenceToIssuesWorkflow(
                    project_repository=SqlAlchemyProjectRepository(session),
                    document_repository=SqlAlchemyDocumentRepository(session),
                    evidence_repository=SqlAlchemyEvidenceRepository(session),
                    fact_repository=SqlAlchemyFactRepository(session),
                    issue_repository=SqlAlchemyIssueRepository(session),
                    fact_extraction_service=FactExtractionService(),
                    fact_validation_service=FactValidationService(),
                    issue_discovery_service=IssueDiscoveryService(),
                    issue_finalization_service=IssueFinalizationService(),
                )
                try:
                    issues = issues_workflow.run(project_id)
                except (ValueError, InvalidStateTransitionError) as exc:
                    st.error(f"이슈 확정 실패: {exc}")
                else:
                    st.success(f"이슈 {len(issues)}건 확정됨.")
                    st.rerun()
        return
    if not _state_at_least(current, WorkflowState.ISSUES_COMPLETED):
        st.info("이 단계는 Evidence 완료 이후에만 실행할 수 있다.")
        return

    with session_scope(factory) as session:
        issues = SqlAlchemyIssueRepository(session).list_by_project(project_id)
    st.success(f"이슈 {len(issues)}건 확정됨.")
    st.dataframe(
        [
            {
                "이슈": issue.label,
                "fact 수": len(issue.fact_ids),
                "문서 수": issue.document_count,
                "출처 수": issue.source_count,
                "채널 수": issue.channel_count,
                "세부 감성": ", ".join(sorted({s.sentiment.value for s in issue.subissues})),
                "세부 입장": ", ".join(sorted({s.stance.value for s in issue.subissues})),
            }
            for issue in issues
        ],
        use_container_width=True,
    )

    st.divider()
    st.subheader("통계 집계 (AnalyticsSnapshot)")
    if current is WorkflowState.ISSUES_COMPLETED:
        settings = get_settings()
        manager = analytics_ui.get_job_manager(settings.database_url)
        job_state = manager.poll()
        same_project = job_state.get("project_id") == str(project_id)
        if job_state.get("status") == "running" and same_project:
            st.info("통계 집계가 백그라운드에서 실행 중이다. 사이드바에서 진행 상황을 볼 수 있다.")
        else:
            st.caption(
                "집계는 별도 프로세스에서 실행된다 — 이 화면을 벗어나거나 새로고침해도 "
                "계속 진행되며, 진행 상황은 사이드바에 표시된다."
            )
            if st.button("통계 집계 실행"):
                run = VersionedRunSchema(
                    run_id=uuid4(),
                    input_version="issues:v1",
                    output_version="analytics:v1",
                    created_at=datetime.now(timezone.utc),
                )
                if manager.submit(project_id, run):
                    st.rerun()
                else:
                    st.error(manager.poll().get("error", "이미 다른 집계가 실행 중이다."))
        return
    if not _state_at_least(current, WorkflowState.ANALYTICS_COMPLETED):
        return

    with session_scope(factory) as session:
        summary = SqlAlchemyAnalyticsRepository(session).get_latest_summary(project_id)
    if summary is not None:
        st.success("통계 집계 완료됨 — '5. 서술 편집'에서 이슈별 초안을 생성할 수 있다.")
        analytics_ui.render_analytics_summary(summary)


def _template_sentences(
    context: NarrativeContext,
    analytics,
    evidence,
) -> list[NarrativeSentenceSchema]:
    """Reuse TemplateNarrativeService's strict, tested per-fact rendering
    (claim must match the linked evidence excerpt verbatim) rather than
    reimplementing a second deterministic template. Tagged role="overview"
    (the default) -- these per-fact quotes stand in for the LLM's
    synthesized background paragraph when no LLM key is configured.
    """

    service = TemplateNarrativeService()
    sentences: list[NarrativeSentenceSchema] = []
    for fact in context.facts:
        if fact.status not in {FactStatus.VERIFIED, FactStatus.SUPPORTED}:
            continue
        try:
            text = service.render_fact(fact, analytics, evidence)
        except ValueError:
            continue  # not supported by linked evidence text, skip rather than crash the page
        sentences.append(NarrativeSentenceSchema(text=text, fact_ids=[fact.fact_id]))
    return sentences


def _template_closing_sentence(issue) -> list[NarrativeSentenceSchema]:
    """A deterministic closing sentence for the no-LLM fallback: the real
    count of subissues per sentiment label, grounded in the issue's own
    fact_ids (the same facts those subissues were classified from) --
    never an estimate (AGENTS.md rule 7)."""

    counts = summarize_subissue_sentiment_counts(issue)
    total = sum(counts.values())
    if not total:
        return []
    text = (
        f"세부 쟁점 {total}건 중 긍정 {counts[SentimentLabel.POSITIVE]}건·"
        f"부정 {counts[SentimentLabel.NEGATIVE]}건·중립 {counts[SentimentLabel.NEUTRAL]}건·"
        f"혼재 {counts[SentimentLabel.MIXED]}건으로 집계됨."
    )
    return [NarrativeSentenceSchema(text=text, fact_ids=issue.fact_ids, role="closing")]


def _load_issue_narrative_materials(session, project_id: UUID, issue_id):
    """Re-fetch the issue/facts/documents a saved NarrativeOutputSchema was
    generated for, so any saved version (not just the one just generated in
    this script run) can be rendered as the overview/table/closing report.
    Returns None if the issue no longer exists (e.g. a legacy output row
    saved before ``issue_id`` existed, or the issue was deleted) -- callers
    fall back to the plain sentence list in that case."""

    issue = SqlAlchemyIssueRepository(session).get(project_id, issue_id)
    if issue is None:
        return None
    fact_repository = SqlAlchemyFactRepository(session)
    facts = [
        fact
        for fact_id in issue.fact_ids
        if (fact := fact_repository.get(project_id, fact_id)) is not None
    ]
    document_repository = SqlAlchemyDocumentRepository(session)
    document_ids = {doc_id for fact in facts for doc_id in fact.evidence_document_ids}
    documents = {
        document.document_id: document
        for doc_id in document_ids
        if (document := document_repository.get(project_id, doc_id)) is not None
    }
    return issue, facts, documents


def _format_issue_sources(facts, documents) -> list[str]:
    ordered_documents = sorted(
        {
            doc_id: documents[doc_id]
            for fact in facts
            for doc_id in fact.evidence_document_ids
            if doc_id in documents
        }.values(),
        key=lambda document: document.published_at or datetime.min.replace(tzinfo=timezone.utc),
    )
    formatted = [
        f"{document.source}({document.published_at.strftime('%Y.%m.%d')})"
        if document.published_at else document.source
        for document in ordered_documents
    ]
    return list(dict.fromkeys(formatted))  # dedupe, keep first-seen order


def _render_narrative_sentences(output: NarrativeOutputSchema) -> None:
    for sentence in output.sentences:
        st.markdown(f"- {sentence.text}")
        refs = []
        if sentence.fact_ids:
            refs.append(f"fact {len(sentence.fact_ids)}건")
        if sentence.evidence_ids:
            refs.append(f"evidence {len(sentence.evidence_ids)}건")
        if sentence.document_ids:
            refs.append(f"document {len(sentence.document_ids)}건")
        if sentence.analytics_paths:
            refs.append("analytics: " + ", ".join(sentence.analytics_paths))
        st.caption("근거 — " + ", ".join(refs))


def _star_cell(label: SentimentLabel) -> str:
    count, text = sentiment_to_stars(label)
    return f"{render_star_rating(count)} {text}"


def _render_issue_narrative_report(output: NarrativeOutputSchema, materials) -> None:
    """The per-issue report layout: overview paragraph -> 핵심 과제 table
    (온라인 반응 as a fixed sentiment->star mapping, see
    app/narrative/reasons.py) -> 출처 -> closing paragraph. Falls back to
    the plain sentence list when the issue can't be resolved."""

    if materials is None:
        _render_narrative_sentences(output)
        return
    issue, facts, documents = materials
    overview = [s for s in output.sentences if s.role == "overview"]
    closing = [s for s in output.sentences if s.role == "closing"]

    st.markdown(f"#### 이슈: {issue.label}")
    if overview:
        st.write(" ".join(sentence.text for sentence in overview))
    if issue.subissues:
        st.dataframe(
            [
                {
                    "핵심 과제": subissue.label,
                    "정책 · 현황": f"{subissue.policy} — {subissue.summary}",
                    "온라인 반응": _star_cell(subissue.sentiment),
                }
                for subissue in issue.subissues
            ],
            use_container_width=True,
        )
    sources = _format_issue_sources(facts, documents)
    if sources:
        st.caption("출처: " + ", ".join(sources))
    if closing:
        st.write(" ".join(sentence.text for sentence in closing))
    with st.expander("근거 보기 (문장별 fact/evidence/document 인용)"):
        _render_narrative_sentences(output)


def page_narrative(factory: sessionmaker) -> None:
    st.header("5. 서술 편집 (LLM 초안)")
    project_id_str = _require_active_project()
    if project_id_str is None:
        return
    project_id = UUID(project_id_str)

    with session_scope(factory) as session:
        workflow = SqlAlchemyProjectRepository(session).get_workflow(project_id)
    if workflow is None:
        st.error("프로젝트를 찾지 못했다.")
        return
    if not _state_at_least(workflow.workflow_state, WorkflowState.ANALYTICS_COMPLETED):
        st.info(
            "이슈 확정과 통계 집계가 끝나야 서술 초안을 만들 수 있다. "
            "'4. 통계·이슈 검토'에서 먼저 실행하라."
        )
        return

    settings = get_settings()
    if settings.gemini_api_key:
        st.caption(
            "Gemini(`gemini-2.5-flash`)로 초안을 생성한다. 모델이 인용한 fact/"
            "evidence/document id와 analytics 경로는 실제 입력과 대조해서, 근거 "
            "없는 문장은 자동으로 버린다(`app/narrative/llm_adapter.py`)."
        )
    else:
        st.caption(
            "`AIPORG2_GEMINI_API_KEY`가 없어 결정론적 템플릿으로만 생성한다"
            "(`app/narrative/template.py`) — 근거 문서 원문과 claim이 정확히 "
            "일치하는 fact만 문장이 된다."
        )

    with session_scope(factory) as session:
        issues = SqlAlchemyIssueRepository(session).list_by_project(project_id)
    if not issues:
        st.info("확정된 이슈가 없다.")
        return

    issue_by_id = {str(issue.issue_id): issue for issue in issues}
    selected_id = st.selectbox(
        "이슈 선택",
        options=list(issue_by_id),
        format_func=lambda key: issue_by_id[key].label,
    )
    issue = issue_by_id[selected_id]

    if st.button("초안 생성"):
        with session_scope(factory) as session:
            fact_repository = SqlAlchemyFactRepository(session)
            facts = [
                fact
                for fact_id in issue.fact_ids
                if (fact := fact_repository.get(project_id, fact_id)) is not None
            ]
            analytics = SqlAlchemyAnalyticsRepository(session).get_latest(project_id)
            evidence = SqlAlchemyEvidenceRepository(session).list_by_project(project_id)
            if analytics is None:
                st.error("통계 집계 결과가 없다.")
                return

            positive_reasons, negative_reasons = derive_narrative_reasons(issue)
            context = NarrativeContext(
                issue=issue,
                facts=facts,
                sentiment=aggregate_issue_sentiment(issue),
                keywords=[issue.label],
                positive_reasons=positive_reasons,
                negative_reasons=negative_reasons,
            )

            if settings.gemini_api_key:
                adapter = GeminiNarrativeAdapter(api_key=settings.gemini_api_key)
                try:
                    output = asyncio.run(
                        adapter.generate(
                            project_id=project_id,
                            context=context,
                            analytics=analytics,
                            evidence=evidence,
                            analytics_run_id=analytics.run.run_id,
                        )
                    )
                except NarrativeGenerationError as exc:
                    st.error(f"Gemini 초안 생성 실패: {exc}")
                    return
            else:
                sentences = _template_sentences(context, analytics, evidence) + (
                    _template_closing_sentence(issue)
                )
                if not sentences:
                    st.warning(
                        "템플릿으로 생성 가능한 문장이 없다(근거 원문과 정확히 "
                        "일치하는 VERIFIED/SUPPORTED fact가 없음)."
                    )
                    return
                output = NarrativeOutputSchema(
                    project_id=project_id,
                    run=VersionedRunSchema(
                        run_id=uuid4(),
                        input_version="narrative-context:v1",
                        output_version="template:v1",
                        created_at=datetime.now(timezone.utc),
                    ),
                    analytics_run_id=analytics.run.run_id,
                    issue_id=issue.issue_id,
                    sentences=sentences,
                )

            SqlAlchemyNarrativeRepository(session).save_output(project_id, output)
        st.success(f"초안 저장됨 — 문장 {len(output.sentences)}개.")
        st.rerun()

    st.divider()
    st.subheader("저장된 버전")
    st.caption(
        "초안은 프로젝트 단위로 저장된다(이슈별 저장이 아님) — 위에서 다른 "
        "이슈를 골라 다시 생성하면 그게 새 버전이 된다. 수정도 새 버전으로 "
        "저장되며 이전 버전은 지워지지 않는다."
    )
    with session_scope(factory) as session:
        outputs = SqlAlchemyNarrativeRepository(session).list_outputs(project_id)
    if not outputs:
        st.info("아직 저장된 초안이 없다.")
        return

    def _version_label(output: NarrativeOutputSchema) -> str:
        source = f"Gemini({output.generation.model})" if output.generation else "템플릿/수정"
        return f"{output.run.output_version} · {output.run.created_at.isoformat()} · {source}"

    labels = [_version_label(output) for output in outputs]

    st.markdown("**보기 및 수정**")
    view_index = st.selectbox(
        "버전 선택", options=range(len(outputs)), format_func=lambda i: labels[i]
    )
    viewing = outputs[view_index]
    with session_scope(factory) as session:
        materials = (
            _load_issue_narrative_materials(session, project_id, viewing.issue_id)
            if viewing.issue_id is not None else None
        )
    _render_issue_narrative_report(viewing, materials)

    with st.form("edit_narrative_form"):
        st.caption("문장 내용만 고칠 수 있다(근거 참조는 그대로 유지됨). 저장하면 새 버전이 된다.")
        _role_label = {"overview": "배경·경과", "closing": "해석·제한"}
        edited_texts = [
            st.text_area(
                f"문장 {i + 1} ({_role_label[sentence.role]})",
                value=sentence.text, key=f"edit-{view_index}-{i}",
            )
            for i, sentence in enumerate(viewing.sentences)
        ]
        save_edit = st.form_submit_button("수정 저장 (새 버전)")

    if save_edit:
        if any(not text.strip() for text in edited_texts):
            st.error("빈 문장은 저장할 수 없다.")
        else:
            edited = viewing.model_copy(update={
                "run": VersionedRunSchema(
                    run_id=uuid4(),
                    input_version=viewing.run.output_version,
                    output_version=f"edited-from:{viewing.run.output_version}",
                    created_at=datetime.now(timezone.utc),
                ),
                "generation": None,
                "sentences": [
                    sentence.model_copy(update={"text": text.strip()})
                    for sentence, text in zip(viewing.sentences, edited_texts)
                ],
            })
            with session_scope(factory) as session:
                SqlAlchemyNarrativeRepository(session).save_output(project_id, edited)
            st.success("수정본이 새 버전으로 저장됐다.")
            st.rerun()

    st.divider()
    st.subheader("승인")
    is_latest_version = view_index == 0
    if viewing.approved:
        st.success(f"이 버전은 승인됨 ({viewing.approved_at.isoformat()}).")
        if is_latest_version and st.button("승인 취소", key="unapprove-narrative"):
            with session_scope(factory) as session:
                SqlAlchemyNarrativeRepository(session).approve_output(
                    project_id, viewing.run.run_id, False, None
                )
            st.rerun()
    else:
        if not is_latest_version:
            st.caption("승인은 최신 버전에서만 가능하다 — 최신 버전을 선택하라.")
        if st.button("이 버전 승인", key="approve-narrative", disabled=not is_latest_version):
            with session_scope(factory) as session:
                SqlAlchemyNarrativeRepository(session).approve_output(
                    project_id, viewing.run.run_id, True, datetime.now(timezone.utc)
                )
            st.success("승인됨.")
            st.rerun()
    st.caption(
        "narrative 승인만으로 최종 보고서가 완성되지 않는다 — '7. 보고서 "
        "미리보기'에서 시각 자료 승인까지 모두 확인한 뒤 최종 승인한다"
        "(docs/aiporg2/visualization-design.md)."
    )

    if len(outputs) >= 2:
        st.divider()
        st.subheader("버전 비교")
        col_a, col_b = st.columns(2)
        index_a = col_a.selectbox(
            "버전 A", options=range(len(outputs)), format_func=lambda i: labels[i], key="compare_a"
        )
        index_b = col_b.selectbox(
            "버전 B", options=range(len(outputs)), format_func=lambda i: labels[i],
            index=min(1, len(outputs) - 1), key="compare_b",
        )
        with session_scope(factory) as session:
            materials_a = (
                _load_issue_narrative_materials(session, project_id, outputs[index_a].issue_id)
                if outputs[index_a].issue_id is not None else None
            )
            materials_b = (
                _load_issue_narrative_materials(session, project_id, outputs[index_b].issue_id)
                if outputs[index_b].issue_id is not None else None
            )
        with col_a:
            _render_issue_narrative_report(outputs[index_a], materials_a)
        with col_b:
            _render_issue_narrative_report(outputs[index_b], materials_b)


def _visualization_version_label(output: VisualizationOutputSchema) -> str:
    status = "승인됨" if output.approved else "미승인"
    return f"{output.run.output_version} · {output.run.created_at.isoformat()} · {status}"


def _render_visualization_items(output: VisualizationOutputSchema) -> None:
    st.caption(output.title)
    rows = [
        {
            "포함": item.included,
            "순서": item.order,
            "라벨": item.label,
            "값": item.value,
            "분류": item.category or "",
            "색상": item.color or "",
            "근거 경로": item.analytics_path,
        }
        for item in sorted(output.items, key=lambda i: i.order)
    ]
    st.dataframe(rows, use_container_width=True)
    chart_data = {item.label: item.value for item in output.items if item.included}
    if chart_data:
        st.bar_chart(chart_data)


def _render_visualization_slot(
    factory: sessionmaker, project_id: UUID, slot_key: str
) -> None:
    with session_scope(factory) as session:
        outputs = SqlAlchemyVisualizationRepository(session).list_outputs(project_id, slot_key)

    if st.button(
        "재생성" if outputs else "생성", key=f"generate-{slot_key}"
    ):
        with session_scope(factory) as session:
            analytics = SqlAlchemyAnalyticsRepository(session).get_latest(project_id)
            if analytics is None:
                st.error("통계 집계 결과가 없다. '4. 통계·이슈 검토'에서 먼저 집계하라.")
                return
            run = VersionedRunSchema(
                run_id=uuid4(),
                input_version=f"analytics:{analytics.run.output_version}",
                output_version=f"v{len(outputs) + 1}",
                created_at=datetime.now(timezone.utc),
            )
            render_service = VisualizationRenderService()
            try:
                if slot_key == CHANNEL_DONUT_SLOT:
                    output = render_service.render_channel_donut(project_id, run, analytics)
                else:
                    output = render_service.render_top10_keywords(project_id, run, analytics)
            except VisualizationRenderError as exc:
                st.error(f"생성 실패: {exc}")
                return
            SqlAlchemyVisualizationRepository(session).save_output(project_id, output)
        st.success("생성됨.")
        st.rerun()

    if not outputs:
        st.info("아직 생성된 버전이 없다.")
        return

    labels = [_visualization_version_label(output) for output in outputs]
    view_index = st.selectbox(
        "버전 선택", options=range(len(outputs)), format_func=lambda i: labels[i],
        key=f"select-{slot_key}",
    )
    viewing = outputs[view_index]
    _render_visualization_items(viewing)
    is_latest_version = view_index == 0

    with st.form(f"edit-{slot_key}"):
        st.caption(
            "값은 AnalyticsSnapshot 집계값 그대로이며 여기서 바꿀 수 없다. "
            "라벨·분류·색상·순서·표시 여부만 수정 가능하다."
        )
        new_title = st.text_input("제목", value=viewing.title, key=f"title-{slot_key}-{view_index}")
        edited_items = []
        for i, item in enumerate(sorted(viewing.items, key=lambda x: x.order)):
            cols = st.columns([3, 2, 2, 1, 1])
            label = cols[0].text_input(
                "라벨", value=item.label, key=f"label-{slot_key}-{view_index}-{i}"
            )
            category = cols[1].text_input(
                "분류", value=item.category or "", key=f"cat-{slot_key}-{view_index}-{i}"
            )
            color = cols[2].text_input(
                "색상", value=item.color or "", key=f"color-{slot_key}-{view_index}-{i}"
            )
            order = cols[3].number_input(
                "순서", value=item.order, step=1, key=f"order-{slot_key}-{view_index}-{i}"
            )
            included = cols[4].checkbox(
                "표시", value=item.included, key=f"incl-{slot_key}-{view_index}-{i}"
            )
            edited_items.append(item.model_copy(update={
                "label": label,
                "category": category or None,
                "color": color or None,
                "order": int(order),
                "included": included,
            }))
        save_edit = st.form_submit_button("수정 저장 (새 버전)")

    if save_edit:
        edited = viewing.model_copy(update={
            "run": VersionedRunSchema(
                run_id=uuid4(),
                input_version=viewing.run.output_version,
                output_version=f"edited-from:{viewing.run.output_version}",
                created_at=datetime.now(timezone.utc),
            ),
            "title": new_title,
            "items": edited_items,
            "approved": False,
            "approved_at": None,
        })
        with session_scope(factory) as session:
            SqlAlchemyVisualizationRepository(session).save_output(project_id, edited)
        st.success("수정본이 새 버전으로 저장됐다 — 재검수 상태(미승인)로 시작한다.")
        st.rerun()

    st.divider()
    if viewing.approved:
        st.success(f"현재 버전 승인됨 ({viewing.approved_at.isoformat()}).")
        if is_latest_version and st.button("승인 취소", key=f"unapprove-{slot_key}"):
            with session_scope(factory) as session:
                SqlAlchemyVisualizationRepository(session).approve_output(
                    project_id, viewing.run.run_id, False, None
                )
            st.rerun()
    else:
        if not is_latest_version:
            st.caption("승인은 최신 버전에서만 가능하다 — 최신 버전을 선택하라.")
        if st.button("이 버전 승인", key=f"approve-{slot_key}", disabled=not is_latest_version):
            with session_scope(factory) as session:
                SqlAlchemyVisualizationRepository(session).approve_output(
                    project_id, viewing.run.run_id, True, datetime.now(timezone.utc)
                )
            st.success("승인됨.")
            st.rerun()

    if len(outputs) >= 2:
        st.divider()
        st.subheader("버전 비교")
        col_a, col_b = st.columns(2)
        index_a = col_a.selectbox(
            "버전 A", options=range(len(outputs)), format_func=lambda i: labels[i],
            key=f"cmp-a-{slot_key}",
        )
        index_b = col_b.selectbox(
            "버전 B", options=range(len(outputs)), format_func=lambda i: labels[i],
            index=min(1, len(outputs) - 1), key=f"cmp-b-{slot_key}",
        )
        with col_a:
            _render_visualization_items(outputs[index_a])
        with col_b:
            _render_visualization_items(outputs[index_b])


def page_visualization(factory: sessionmaker) -> None:
    st.header("6. 시각 자료 편집·승인")
    project_id_str = _require_active_project()
    if project_id_str is None:
        return
    project_id = UUID(project_id_str)

    with session_scope(factory) as session:
        workflow = SqlAlchemyProjectRepository(session).get_workflow(project_id)
    if workflow is None:
        st.error("프로젝트를 찾지 못했다.")
        return
    if not _state_at_least(workflow.workflow_state, WorkflowState.ANALYTICS_COMPLETED):
        st.info("통계 집계가 끝나야 시각 자료를 만들 수 있다. '4. 통계·이슈 검토'에서 먼저 실행하라.")
        return

    st.caption(
        "VIS-02(채널 도넛)·VIS-07(TOP10 키워드) 2종만 먼저 연결했다(1차 최소 "
        "단위, docs/aiporg2/visualization-design.md). 값은 AnalyticsSnapshot "
        "집계값 그대로이며 UI에서 직접 숫자를 바꿀 수 없다."
    )

    tabs = st.tabs(list(VISUALIZATION_SLOTS.values()))
    for (slot_key, _slot_title), tab in zip(VISUALIZATION_SLOTS.items(), tabs):
        with tab:
            _render_visualization_slot(factory, project_id, slot_key)


def page_report(factory: sessionmaker) -> None:
    st.header("7. 보고서 미리보기")
    project_id_str = _require_active_project()
    if project_id_str is None:
        return
    project_id = UUID(project_id_str)

    with session_scope(factory) as session:
        narrative_output = SqlAlchemyNarrativeRepository(session).get_latest_output(project_id)
        visualization_repo = SqlAlchemyVisualizationRepository(session)
        slot_outputs = {
            slot_key: visualization_repo.get_latest_output(project_id, slot_key)
            for slot_key in VISUALIZATION_SLOTS
        }
        latest_report = SqlAlchemyReportRepository(session).get_latest(project_id)

    st.subheader("승인 상태")
    rows = [{
        "항목": "서술(narrative)",
        "승인됨": bool(narrative_output and narrative_output.approved),
    }]
    for slot_key, title in VISUALIZATION_SLOTS.items():
        output = slot_outputs[slot_key]
        rows.append({"항목": title, "승인됨": bool(output and output.approved)})
    st.dataframe(rows, use_container_width=True)

    all_approved = all(row["승인됨"] for row in rows)
    st.caption(
        "포함된 모든 자료(narrative + 시각 자료 2종)의 현재 버전이 승인되어야 "
        "최종 승인할 수 있다. '5. 서술 편집'·'6. 시각 자료 편집·승인'에서 미승인 "
        "항목을 먼저 승인하라."
    )
    if st.button("최종 승인 (보고서 생성)", disabled=not all_approved):
        report = None
        missing: list[str] | None = None
        with session_scope(factory) as session:
            service = ReportApprovalService(
                SqlAlchemyNarrativeRepository(session),
                SqlAlchemyVisualizationRepository(session),
                SqlAlchemyReportRepository(session),
            )
            try:
                report = service.approve(project_id, now=datetime.now(timezone.utc))
            except ReportApprovalError as exc:
                missing = exc.missing
        # st.rerun() raises internally to halt the script -- it must run
        # after the `with` block above has already committed, or the
        # commit never happens and session_scope's except-clause rolls
        # back the just-created report instead.
        if missing is not None:
            st.error(f"최종 승인 실패 — 미승인 항목: {', '.join(missing)}")
        else:
            st.success(f"보고서 생성됨: `{report.report_id}`")
            st.rerun()

    if latest_report is not None:
        st.divider()
        st.subheader("가장 최근 승인본")
        st.caption(
            f"report_id: `{latest_report.report_id}` · "
            f"생성: {latest_report.run.created_at.isoformat()} · "
            f"포함된 시각 자료 {len(latest_report.visualizations)}건"
        )
        st.caption(
            "현재 Report.context는 승인된 narrative 문장이 아니라 입력 "
            "NarrativeContext를 그대로 담는다 — 알려진 범위 제한"
            "(docs/aiporg2/visualization-design.md '알려진 범위 제한' 참고). "
            "승인된 실제 문장은 '5. 서술 편집'에서 계속 조회할 수 있다."
        )


def page_output(factory: sessionmaker) -> None:
    st.header("8. 출력·이력")
    project_id_str = _require_active_project()
    if project_id_str is None:
        return
    project_id = UUID(project_id_str)

    st.caption(
        "DOCX/Markdown writer와 전체 12쪽 HWPX 조립은 아직 미구현(M5/M6). "
        "아래는 표지+목차+요약 3쪽짜리 HWPX 시제품만 내려받을 수 있다 — 이 "
        "환경에는 실제 한컴이 없어 열림·배치 검증을 못 했으니, 받은 파일을 "
        "직접 한컴에서 열어 확인해야 한다(docs/aiporg2/visualization-design.md, "
        "HANDOFF.md 16차 '검증 못 한 부분' 참고)."
    )

    with session_scope(factory) as session:
        project = SqlAlchemyProjectRepository(session).get(project_id)
        report = SqlAlchemyReportRepository(session).get_latest(project_id)
        narrative_output = SqlAlchemyNarrativeRepository(session).get_latest_output(project_id)
        visualization_repo = SqlAlchemyVisualizationRepository(session)
        visualization_outputs = {
            slot_key: visualization_repo.get_latest_output(project_id, slot_key)
            for slot_key in VISUALIZATION_SLOTS
        }

    if project is None:
        st.error("프로젝트를 찾지 못했다.")
        return
    if report is None or narrative_output is None or any(
        output is None for output in visualization_outputs.values()
    ):
        st.info("먼저 '7. 보고서 미리보기'에서 최종 승인을 완료해야 HWPX 시제품을 만들 수 있다.")
        return

    try:
        raw = build_cover_toc_summary(
            report, narrative_output, visualization_outputs,
            title=f"{project.name} 온라인여론 키워드조사 분석 보고서",
        )
    except HwpxPrototypeError as exc:
        st.error(f"HWPX 시제품 생성 실패: {exc}")
        return

    st.success(f"report_id `{report.report_id}` 기준으로 생성했다.")
    st.download_button(
        "HWPX 시제품 다운로드 (표지/목차/요약 3쪽)",
        data=raw,
        file_name=f"{project.name}-prototype.hwpx",
        mime="application/hwp+zip",
    )


@st.fragment(run_every=3)
def _render_analytics_job_sidebar_status() -> None:
    """Polls the one shared background job manager on a timer so the
    sidebar reflects progress across page changes and browser reloads
    without a full-page rerun."""

    settings = get_settings()
    manager = analytics_ui.get_job_manager(settings.database_url)
    analytics_ui.render_job_sidebar_status(manager.poll())


def main() -> None:
    st.set_page_config(page_title="AIPORG 2.0 콘솔", layout="wide")
    st.sidebar.title("AIPORG 2.0")
    _render_analytics_job_sidebar_status()
    page = st.sidebar.radio(
        "화면",
        [
            "1. 월별 프로젝트",
            "2. 수집 설정·실행",
            "3. 수집 결과 검토",
            "4. 통계·이슈 검토",
            "5. 서술 편집 (LLM 초안)",
            "6. 시각 자료 편집·승인",
            "7. 보고서 미리보기",
            "8. 출력·이력",
        ],
    )
    factory = get_session_factory()

    if page == "1. 월별 프로젝트":
        page_project(factory)
    elif page == "2. 수집 설정·실행":
        page_collect(factory)
    elif page == "3. 수집 결과 검토":
        page_progress(factory)
    elif page == "4. 통계·이슈 검토":
        page_analytics(factory)
    elif page == "5. 서술 편집 (LLM 초안)":
        page_narrative(factory)
    elif page == "6. 시각 자료 편집·승인":
        page_visualization(factory)
    elif page == "7. 보고서 미리보기":
        page_report(factory)
    else:
        page_output(factory)


if __name__ == "__main__":
    main()
