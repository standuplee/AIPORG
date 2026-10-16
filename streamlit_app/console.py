"""AIPORG 2.0 Streamlit console (M4 minimal unit).

Scope decided 2026-10-16: no fixed base search terms, the monthly keyword
list typed here is the entire search scope; comments are collected (see
``docs/aiporg2/narrative-design.md`` and the implementation plan for the
``metadata["document_type"]`` convention, not wired into collectors yet);
LLM drafting is an API-based adapter with the key supplied later; X and
Instagram are out of scope (paid access), Google is in scope but has no
collector implemented yet.

This page only wires together existing ``app/`` contracts (repositories,
collection service, enums). It adds no new schema. Narrative drafting,
visualization/report approval, and HWPX/DOCX/MD export are not implemented
yet (see the M0/M3/M5 sections of
``docs/superpowers/plans/2026-09-08-aiporg2-implementation.md``) and are
shown here as explicit "not implemented" panels rather than placeholders
that look functional.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
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

from app.cleaning.service import CleaningService
from app.collectors.daum_news import DaumNewsCollector
from app.collectors.naver_news import NaverNewsCollector
from app.core.config import Settings, get_settings
from app.core.enums import ChannelType, CollectionRunStatus, WorkflowState
from app.core.state_machine import InvalidStateTransitionError
from app.db.session import create_session_factory, session_scope
from app.dedup.service import DeduplicationService
from app.evidence.service import EvidenceService
from app.models.project import Query
from app.repositories.sqlalchemy import (
    SqlAlchemyCollectionRunRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyDuplicateClusterRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyQuerySetRepository,
)
from app.schemas.common import AnalysisPeriodSchema, ComparisonPeriodSchema, TargetSchema
from app.schemas.project import ProjectCreate
from app.schemas.query import SearchQuery
from app.workflows.multi_query_collection_to_evidence import (
    CollectionRequest,
    MultiQueryCollectionToEvidenceWorkflow,
)

# label -> settings credential key used to build the real collector.
IMPLEMENTED_PROVIDERS = ["naver", "daum"]
PROVIDER_LABELS = {"naver": "네이버 뉴스", "daum": "다음 뉴스"}
PLANNED_PROVIDERS = [
    "구글 검색 (범위 포함, 수집기 미구현 — M1)",
    "커뮤니티: 클리앙/디시인사이드/펨코/루리웹/더쿠 (목록 확정, 수집기 포팅 전 — M1)",
    "유튜브 (1.0 코드 존재, 2.0 포팅 전 — M1)",
]
NOT_IMPLEMENTED_PAGES = {
    "서술 편집 (LLM 초안)": (
        "M3(LLM adapter)가 아직 없다. 템플릿 서술(`app/narrative/template.py`)만 "
        "존재하며 출력/승인 계약(M0)도 결정 전이다."
    ),
    "시각 자료 편집·승인": (
        "M0에서 Visualization 계약을 결정하기 전까지 구현하지 않는다. "
        "`app/schemas/visualization.py`는 아직 빈 contract다."
    ),
    "보고서 미리보기": (
        "Report bundle 계약(M0)과 승인 게이트가 결정되지 않아 조립할 대상이 없다."
    ),
    "출력·이력": (
        "python-hwpx 연결, 2.0 DOCX/Markdown writer, 승인 게이트가 모두 M5/M6 "
        "예정 작업이라 아직 출력할 수 없다."
    ),
}


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
            "위에 입력한 줄 전체가 이번 수집의 검색어다."
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
        for label in PLANNED_PROVIDERS:
            st.checkbox(f"{label}", value=False, disabled=True)

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
    queries = [SearchQuery(query=keyword, channels=[ChannelType.NEWS]) for keyword in keywords]

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
                query=SearchQuery(query=keyword, channels=[ChannelType.NEWS]),
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
        "감성 분류·연관 키워드·비교기간 등 전체 AnalyticsSnapshot 집계(M2)는 "
        "아직 이 화면에 연결하지 않았다 — 아래는 Evidence까지 간 결과의 원자료 확인용이다."
    )

    with session_scope(factory) as session:
        canonical_documents = SqlAlchemyDocumentRepository(session).list_canonical(project_id)
        evidence = SqlAlchemyEvidenceRepository(session).list_by_project(project_id)

    col1, col2 = st.columns(2)
    col1.metric("고유(canonical) 문서 수", len(canonical_documents))
    col2.metric("Evidence 수", len(evidence))

    if not canonical_documents:
        st.info("아직 Evidence까지 도달한 문서가 없다. 먼저 수집을 실행하라.")
        return

    st.subheader("고유 문서 목록")
    st.dataframe(
        [
            {
                "제목": document.title,
                "출처": document.source,
                "채널": document.channel.value if document.channel else None,
                "게시일": document.published_at.isoformat() if document.published_at else None,
                "URL": document.canonical_url,
            }
            for document in canonical_documents
        ],
        use_container_width=True,
    )


def page_not_implemented(title: str, reason: str) -> None:
    st.header(title)
    st.warning("미구현")
    st.write(reason)
    st.caption(
        "상세는 docs/superpowers/plans/2026-09-08-aiporg2-implementation.md의 "
        "M0/M3/M5 절 참고."
    )


def main() -> None:
    st.set_page_config(page_title="AIPORG 2.0 콘솔", layout="wide")
    st.sidebar.title("AIPORG 2.0")
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
    else:
        title = page.split(". ", 1)[1]
        page_not_implemented(page, NOT_IMPLEMENTED_PAGES[title])


if __name__ == "__main__":
    main()
