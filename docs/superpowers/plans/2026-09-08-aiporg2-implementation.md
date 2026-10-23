# AIPORG 2.0 Implementation Plan

## 2026-10-16 사용자 요구 개정: 월간 키워드 보고서

이 절은 아래 기존 계획 및 과거 완료 기록과 충돌할 때 우선한다. 상세 요구와 인수 조건은 [월간 키워드 보고서 명세](../../aiporg2/monthly-keyword-report-requirements.md)에 기록했다.

최종 목표는 월별 키워드 4~5개에 대해 여러 온라인 출처를 수집하고, 사용자가 제공한 **7월 보고서 12쪽의 구성·서술·표·인포그래픽을 재현하는 HWPX 중심 보고서**를 만드는 것이다. 키워드가 바뀌면 사실·통계·표·그림·출처를 새로 생성한다. GPT/Claude가 근거 기반 초안을 작성하고 Streamlit에서 사용자가 검수·수정·승인한 동일 버전만 HWPX·DOCX·Markdown으로 출력한다.

현재 Phase 3~5 완료는 당시 범위의 기록이다. 네이버·다음 뉴스 중심 경로, 기존 라벨 집계, 단순 키워드 집계를 모든 채널의 실제 월간 수집·감성 분류·연관어 분석 완료로 간주하지 않는다. 실제 플랫폼 접근 범위와 페이지 순회, 기간·중복·미수집 처리부터 보완한다.

### 개정 실행 순서

| 순서 | 기존 단계 연결 | 구현 작업 | 완료 게이트 |
| --- | --- | --- | --- |
| M0 | Phase 6 계약 선행 | 문장 근거·초안·수정·승인·그림 버전 계약, 보고서 스타일·가변 블록 | 기존 계약과 차이 문서화 및 명시적 결정 |
| M1 | Phase 3 보완 | 실제 채널 접근 검증, 월간 수집, 검색 경로/원문 채널 분리, 댓글·재시도 | 확보 범위·누락 상태 공개, 중복 없는 재개 |
| M2 | Phase 4~5 보완 | 이슈별 근거, 한국어 TOP20, 대상별 감성, 비교기간 지표 | 재현 가능한 분모·수치·출처 |
| M3 | Phase 6 | GPT/Claude adapter, 장별 초안·검증·버전 저장 | 근거 없는 사실·수치 차단 |
| M4 | Phase 6 UI | Streamlit 편집·근거 비교·재검증·승인 | 영속 저장, 변경 시 재승인, 미승인 export 차단 |
| M5 | Phase 7 | 데이터 기반 표·인포그래픽, 별도 python-hwpx 의존성, 7월 HWPX 템플릿 | 실제 한컴 열림·편집·전체 페이지 시각 검수 |
| M6 | Phase 7~8 | 동일 승인본 DOCX/MD, 월간 복제·출력 이력·API/CLI | 월간 실행부터 승인·3형식 출력까지 통합 통과 |

기존 Phase 6의 template-only 구현은 fallback/기초 테스트로 유지하지만 최종 요구를 충족하지 않는다. 기존의 문장 문자열 완전 일치 검증은 생성형 초안·사용자 편집 전체에 적용하지 않고, 사실·수치·근거 검증과 사람의 검수를 결합한다. Phase 7은 DOCX 단독 우선이 아니라 HWPX 중심의 공통 승인 콘텐츠 출력으로 개정한다.

일반 표와 본문은 편집 가능한 객체로, 복잡한 인포그래픽은 실제 집계값 기반 이미지로 생성한다. 전체 페이지를 이미지로 붙여 HWPX를 만드는 방식은 요구를 충족하지 않는다. 4개 이슈는 12쪽을 기본 목표로 하되 5개 이슈·장문은 페이지를 늘린다. 목차는 최종 페이지를 반영한다.

추가 사용자 요구: **표·그림·차트·인포그래픽은 생성 이후 UI에서 개별 확인·수정·승인**한다. 상세 명세 8.1절에 유형별 편집 범위, 원자료 수정, 재렌더링, 버전 비교, 개별 승인 및 최종 승인 게이트를 기록했다. M4는 편집·승인 화면과 저장을, M5는 편집 가능한 데이터/설정과 렌더 결과를 제공한다. M4→M5 한 방향으로 끝나지 않고 생성→수정→재렌더→개별 승인→문서 배치 검수를 반복한다. 이미지 파일만 저장해서는 요구를 충족하지 않는다.

필수 인수 시나리오는 상세 명세 AT-01~21을 사용한다. 각 모듈 unit test와 단계별 integration test, 기존 1.0 회귀 게이트는 유지한다. 문서 개정만 완료했으며 수집·LLM·UI·HWPX 기능 구현과 새 테스트 실행은 아직 하지 않았다.

## 2026-10-16 코드 검증 기반 상세 구현 계획

이 절은 `HANDOFF.md`, 위 요구 개정, `docs/aiporg2/monthly-keyword-report-requirements.md`,
`docs/aiporg2/narrative-design.md`를 실제 코드(`app/`, `aiporg/`, `tests_v2/`)와 대조해
작성했다. 아래 8절 "진행 기록"은 해당 시점 범위의 개발 이력일 뿐이며, 이번 절의
코드 확인 결과를 현재 상태 판단 기준으로 쓴다. 이번 세션은 문서만 작성했고
코드는 변경하지 않았다.

### 1. 현재 구현 vs 부족 기능 (코드 확인)

**실제로 동작하는 부분**

- `app/core`: enum(`WorkflowState`, `CollectionRunStatus`, `FactStatus`, `ChannelType`,
  `SentimentLabel`, `ConfidenceGrade`), 설정, 로깅, state machine.
- `app/db/session.py`, `app/repositories/sqlalchemy.py`: session factory와 모든
  repository protocol의 concrete 구현.
- `app/collection/service.py` + `app/collectors/{naver_news,daum_news,transport}.py`:
  수집 orchestration. **정정(2026-10-16 4차 세션, 코드로 재확인):
  `naver_news.py`는 `start=1, display=100` 고정 단일 요청만 하지만,
  `daum_news.py`는 `while True`로 `meta.is_end`까지 반복 조회하는 페이지 순회를
  이미 구현하고 있다.** 이전 개정의 "naver_news.py/daum_news.py 모두 단일 요청만"
  서술은 daum 쪽이 부정확했다 — daum은 전체 페이지 순회가 있고, 월경계 등 날짜
  기준 조기 종료 조건만 없다. naver만 첫 페이지(최대 100건) 고정이 실제 제약이다.
- `app/cleaning`, `app/dedup`, `app/evidence`: 정제·3단계 중복 제거·evidence 생성.
- `app/facts/{extraction,validation}.py`, `app/issues/{discovery,finalization}.py`:
  evidence 첫 문장을 그대로 쓰는 deterministic fact 추출과 issue 확정.
- `app/analytics/{service,channel}.py`: 기존 metadata 감성 라벨 집계뿐(자동 분류
  없음), 키워드는 2자 이상 문자 토큰 빈도(형태소 분석 아님) — `docs/aiporg2/analytics.md`와
  일치.
- `app/workflows/*`: collection→evidence, evidence→issues, issues→analytics 3개
  workflow.
- `app/narrative/template.py` + `app/schemas/narrative.py`: deterministic template
  renderer. `NarrativeContext`는 입력 전용(`issue, facts, sentiment, keywords,
  positive_reasons, negative_reasons`)이며 출력 문장/근거 매핑/버전 schema가 없다.

**코드에 없음 (grep/파일 확인, "기록상 완료"로 오인하면 안 되는 부분)**

- `streamlit`, `hwpx` 문자열이 `app/` 전체에 없음 → 검수 UI, HWPX 연동 0% 구현.
- `openai`/`anthropic`/`gpt`/`llm` 실제 코드 없음(매칭된 2곳은 "LLM 호출 금지"
  docstring) → LLM adapter 0% 구현.
- `app/models/report.py`(41줄), `app/schemas/report.py`(33줄),
  `app/models/visualization.py`(21줄), `app/schemas/visualization.py`(22줄)와 대응
  repository(각 17줄): contract만 있는 빈 틀. 렌더링 엔진, 차트 생성, DOCX/HWPX
  writer가 `app/` 2.0에 전혀 없다.
- `app/collectors/`에는 naver_news/daum_news만 있다. 구글 발견 경로, X, 인스타그램,
  유튜브, 커뮤니티, 블로그 collector가 2.0에 없다.
- narrative-design.md가 "결정 대기"로 표시한 출력 계약, 요구사항 §8.1이 요구하는
  시각 자료 버전·승인 schema가 전혀 없다.
- 이번 세션 실행 환경(`/usr/bin/python3` 3.9.6, Xcode 제공)에는 `pytest`/`sqlalchemy`가
  설치되어 있지 않아 `tests_v2`를 실행하지 못했다. `requirements-dev.txt`는 있지만
  **이 쉘에서 재현 가능한 테스트 환경이 실제로 동작하는지 확인하지 못한 상태다.**

**재사용 가능한 1.0 자산 (2.0에 아직 연결 안 됨)**

- `aiporg/charts/{render.py 362줄, infographic.py 331줄, keyword_render.py}`:
  기존 차트/인포그래픽 렌더링 코드. VIS-01~09 구현 시 참고·일부 포팅 대상.
- `aiporg/report/{docx_writer.py 503줄, keyword_docx_writer.py 115줄}`: 기존 DOCX
  writer. 요구 §10대로 차트 미사용 부분이 있어 그대로 최종 템플릿으로 못 쓰지만
  조립 구조는 참고 가능.
- `aiporg/collect/blog.py`, `aiporg/collect/community/*`
  (clien/dcinside/fmkorea/ruliweb/theqoo 사이트 어댑터 포함): 블로그·커뮤니티 수집기
  기존 구현. 2.0 collector 계약에 맞게 재작성 필요하나 사이트별 파싱 로직은
  재사용 가치가 크다.
- `aiporg/youtube/{collector.py, api.py, comments.py, config.py, analyzer/*}`: 유튜브
  수집·댓글·분석기 기존 구현. 2.0 analyzer 규칙(웹 요청 금지)에 맞게 수집과 분석을
  분리해서 포팅해야 한다.
- 구글 발견 경로, X, 인스타그램 전용 코드는 1.0에도 없다 — 신규 구현 또는 범위
  재확인 대상.

### 2. 데이터 계약·저장 구조 변경안

AGENTS.md 1번 규칙에 따라 아래는 모두 **구현 전 명시적 결정이 필요한 제안**이다.

**(a) Narrative 출력/초안/승인 계약** — `narrative-design.md` 권장안
(`NarrativeSentenceSchema`, `NarrativeOutputSchema`, 기존 `narratives.context` JSON
envelope, `save_output`/`get_latest_output`)을 1차 채택한다. 이 권장안은 결정론적
template 출력만 다루므로 LLM 흐름을 위해 추가 결정이 필요하다.

- LLM 실행 메타데이터(provider, model, prompt_version, input_snapshot_hash, usage,
  generated_at)는 신규 테이블 대신 같은 JSON envelope 안 `generation` 블록으로 제안.
- 초안→사용자 수정 이력은 수정마다 새 `run`으로 저장하는 방식을 제안(기존
  `VersionedRunSchema`의 run/input_version/output_version과 가장 자연스럽게 맞음).
- 승인(approval)은 narrative 자체가 아니라 아래 (c) Report 계약에서 narrative
  version + analytics_run_id + 시각자료 version 목록 + template version을 함께
  묶는 방식을 제안.

**(b) Visualization 계약 확장** — 현재 `app/schemas/visualization.py`는 빈 contract다.
`narrative-design.md`와 같은 절차로 별도 설계 문서(`docs/aiporg2/visualization-design.md`
신설 제안)를 먼저 쓴다. 다룰 필드(제안, 결정 전):
`asset_id`, `kind`(table/chart/infographic/image), `slot`(배치 위치),
`source_data_ref`(analytics snapshot 경로+입력 해시), `render_config`(열/정렬/색상/계열/
축/캡션 등 편집 설정 JSON), `rendered_output_ref`, `rendered_at`, `version`,
`previous_version_ref`, `approval_status`(draft/pending_review/approved/superseded),
`approved_by`, `approved_at`.

**(c) Report 계약 확장** — `app/models/report.py`/`schemas/report.py`를 "승인 콘텐츠
bundle" 레코드로 확장하는 안을 제안: `narrative_output_version`, `analytics_run_id`,
`visualization_version_map`(slot→version), `template_version`, 생성 artifact 경로
(`hwpx_path`,`docx_path`,`md_path`), `checksum`, `generated_at`. 요구 §8.1의
"포함된 모든 시각 자료의 현재 버전이 승인되어야 최종 승인"을 이 레코드 생성 조건으로
구현하는 것을 제안.

**(d) Collection 상태 세분화** — 현재 `CollectionRunStatus`는 `PENDING/RUNNING/
COMPLETED/FAILED` 4종뿐이고 요구 §3.4의 "일부 성공/인증 필요/한도 초과/미지원"
구분이 없다. enum 값 추가 전 workflow state 전이와의 상호작용을 설계 문서에 먼저
기록하고 결정한다.

**(e) Workflow state와 검수 상태 분리** — `WorkflowState`에는 이미 `VISUALS_COMPLETED`,
`REPORT_COMPLETED`가 있지만 "초안/검증 필요/검수 중/승인" 같은 사람 검수 상태는
없다. 기존 enum을 바꾸지 않고, 검수 상태는 narrative/visualization/report 레코드의
`approval_status` 필드로 표현하는 것을 제안한다.

### 3. 단계별 작업·의존성·수정 대상 파일

M0~M6는 위 표의 틀을 그대로 쓰고, 각 M에 파일 단위 작업을 붙인다. 각 M은 앞 M의
완료 게이트를 통과해야 시작한다.

**M0. 계약 확정** (의존성 없음)
- 신규: `docs/aiporg2/visualization-design.md`(2b), Report 계약 개정 절(2c, 기존
  `narrative-design.md` 또는 신규 `report-design.md`).
- 결정 후에만 `app/schemas/narrative.py`(출력 모델), `app/schemas/visualization.py`,
  `app/schemas/report.py`, `app/repositories/narrative.py`
  (`save_output`/`get_latest_output`), `app/repositories/visualization.py`,
  `app/repositories/report.py`, `app/core/enums.py`(CollectionRunStatus 값) 수정.
- 산출물: 데이터 계약 문서 + 결정 기록. 코드 변경 없음.

**M1. 실제 수집 범위 확보** (M0과 병행 가능)
1. ~~`app/collectors/naver_news.py`에 페이지 순회 추가~~ — **완료(2026-10-16,
   5차)**: `start<=1000`까지 페이징한다. `app/collectors/daum_news.py`는 이미
   `meta.is_end`까지 순회하므로 월경계 조기 종료 조건만 아직 남아 있음. 키워드
   N개 반복 호출 orchestration도 **완료**: `app/collection/service.py`가 아니라
   신규 `app/workflows/multi_query_collection_to_evidence.py`
   (`MultiQueryCollectionToEvidenceWorkflow`)로 구현했고 Streamlit 콘솔에
   연결했다(아래 "2026-10-16 수집 정확도와 파이프라인 연결 (5차)" 절 참고).
2. 구글 수집기를 신규로 만든다(1.0에도 코드가 없다 — 2026-10-16 결정으로 범위에는
   포함됨). 사용 가능한 검색 인터페이스를 먼저 확인한다(5절 참고).
3. `aiporg/collect/blog.py`, `aiporg/collect/community/*`(clien/dcinside/fmkorea/
   ruliweb/theqoo — 2026-10-16 결정으로 목록 그대로 진행) 참고해 2.0
   `app/collectors/blog_*.py`, `app/collectors/community_*.py` 신규 작성(2.0
   `CollectorProtocol` 준수, repository 외 DB write 없음).
4. `aiporg/youtube/*` 참고해 2.0 collector로 분리 포팅(`app/collectors/youtube.py`).
   분석 로직(`aiporg/youtube/analyzer/*`)은 수집기에 포함하지 않고 Phase 4/5 analyzer
   쪽으로 넘긴다(AGENTS.md 4,5번).
5. X, 인스타그램은 **2026-10-16 결정으로 1차 범위에서 제외**(유료 접근 불가 판단).
   어댑터를 만들지 않는다.
- 수정 파일: `app/collectors/*`, `app/collection/service.py`,
  `tests_v2/unit/test_*_collector*.py` 신규/확장.

**M2. 분석 데이터·근거 보완** (M1의 실제 데이터 형태 확정 후)
- `app/analytics/service.py`: 한국어 TOP20 정규화 로직, 대상별(정책/인물/재난 등)
  감성 분류 입력 확장.
- `app/facts/validation.py`, `app/issues/finalization.py`: 이슈-근거 매핑 보강,
  외부 조사 별도 입력 경로(§3.4 미확정) 연결.

**M3. LLM 초안 저장** (M0 narrative 출력 계약 결정 완료 후)
- 신규: `app/narrative/llm_adapter.py`(provider 호출 경계), `app/narrative/draft_service.py`
  (장/이슈 단위 생성, 재시도, 부분 재생성), `app/narrative/validation.py`(근거 없는
  숫자/고유명사 차단, template 경로와 공유).
- 수정: `app/repositories/narrative.py`, 신규 `app/workflows/narrative_draft_workflow.py`.
- 실제 키 연결 전 mock adapter로 먼저 검증.

**M4. Streamlit 검수·승인 UI** (M0 전체 계약 + M3 초안 저장 후)
- 신규 최상위 디렉터리: `streamlit_app/`(2.0 앱과 분리된 조회/수정 클라이언트). UI도
  `app/repositories/*`를 통해서만 읽고 쓴다(직접 DB write 금지).
- 화면 8개(§8 표): 월별 프로젝트, 수집 설정·실행, 수집 결과 검토, 통계·이슈 검토,
  서술 편집, 시각 자료 편집·승인, 보고서 미리보기, 출력·이력.
- UI 조회용 repository 메서드가 부족하면 M0 결정 범위 내에서 추가.

**M5. 시각 요소·HWPX 템플릿** (M2 analytics, M0 visualization 계약 후, M4와 반복)
- 신규: `app/visualization/engine.py`(VIS-01~09, `aiporg/charts/render.py`/
  `infographic.py` 참고·포팅), `app/visualization/service.py`(편집 설정 반영
  재렌더링).
- python-hwpx 별도 저장소 clone/fork(아직 미완료) 후 `app/report/hwpx_writer.py`
  (신규) 구현.
- 신규 `app/report/assembler.py`: 승인된 narrative+visualization+template을
  조립해 HWPX/DOCX/MD 공통 입력 생성.
- `aiporg/report/docx_writer.py`는 참고하되 그대로 재사용하지 않음.

**M6. 다중 출력·월간 운영** (M5 완료 후)
- 신규 `app/report/docx_writer.py`(2.0), `app/report/markdown_writer.py`(공통
  assembler 입력 사용).
- 월간 프로젝트 복제·전월 비교 연결.
- API/CLI(기존 Phase 8 범위): project 생성/실행/상태조회/report 조회 entrypoint.

### 4. 단계별 테스트·완료 기준

| M | unit test 대상 | integration/완료 기준 |
| --- | --- | --- |
| M0 | 없음(문서화 단계) | 데이터 계약 문서 결정 완료, 기존 `tests_v2/contracts/*` 무변경 통과 |
| M1 | 신규 collector별 pagination/종료조건/중복방지 | 재시도 시 문서 중복 증가 없음, 채널별 상태(성공/부분/실패) 구분 저장 |
| M2 | TOP20 재현성, 대상별 감성 분류 | 동일 입력 동일 출력, 0건/단일채널/비교기간없음 케이스 통과 |
| M3 | 근거 없는 숫자/고유명사 차단, 입력 스냅샷 해시 일치, mock adapter 재시도 | 실패 시 기존 초안 보존, 동일 입력 중복 호출 없음 |
| M4 | repository 조회/저장 메서드 | 새로고침·재시작 후 편집·승인 유지, 미승인 버전 export 차단 |
| M5 | VIS-01~09 각 렌더러(집계값→결과 일치) | 실제 한컴 HWPX 열기·표 편집·전체 페이지 검수(AT-15), 4/5 이슈 페이지 확장(AT-12) |
| M6 | docx/markdown writer | 동일 승인본 3형식 일치(AT-14, AT-21), 월간 복제 후 전월 비교 통과 |

AT-01~21 전체를 최종 수용 기준으로 유지하고 각 M 완료 시 관련 AT를 확인한다.
모든 단계에서 기존 1.0(`tests/`)·2.0(`tests_v2/`) 전체 테스트 통과를 게이트로
유지한다. **이번 세션은 로컬 Python(3.9.6, pytest 미설치)에서 `tests_v2`를
실행하지 못했다. M0 착수 전 `requirements-dev.txt` 기준 가상환경을 구성하고
현재 테스트가 실제로 통과하는지 먼저 재확인해야 한다.**

### 5. 플랫폼별 실제 수집 가능 범위와 확인할 사항

| 플랫폼 | 범위 결정(2026-10-16) | 현재 코드 상태 | 확인할 사항 |
| --- | --- | --- | --- |
| 네이버 | 포함 | `app/collectors/naver_news.py`, **2026-10-16 5차에서 `start<=1000`까지 페이지 순회 추가함**(이전엔 단일 요청 100건 한도) | API 쿼터, 검색 유형별 기간 제한, 본문 확보 범위, 월경계 조기 종료(아직 없음) |
| 다음 | 포함 | `app/collectors/daum_news.py`, `meta.is_end`까지 **이미 페이지 순회함**(정정: 단일 요청 아님). kakao 기반 수집기가 커밋에 별도 존재 | kakao API 키/쿼터, 실제 반환 도메인, 날짜 필터 정확도, 월경계 조기 종료 조건 추가 필요 |
| 구글 | **포함(결정됨)** | 2.0/1.0 모두 코드 없음 | 사용 가능한 검색 인터페이스(공식 API vs 스크래핑 약관), 검색일-게시일 차이 |
| X | **제외(결정됨 — 유료 접근 불가 판단)** | 코드 없음 | 재검토 필요 시 API 인증 등급·비용부터 재확인 |
| 인스타그램 | **제외(결정됨 — 유료 접근 불가 판단)** | 코드 없음 | 재검토 필요 시 계정/권한별 가능 범위부터 재확인 |
| 유튜브 | 포함(순서는 미해결) | `aiporg/youtube/*`(1.0)에 수집기·API·댓글·분석기 존재, 2.0 미포팅 | 게시일 구분 재검증, API 쿼터, 자막 확보 여부, 분석 로직 분리 필요 |
| 커뮤니티 | **포함, 목록은 1.0 그대로 진행(결정됨)** | `aiporg/collect/community/*`(1.0)에 clien/dcinside/fmkorea/ruliweb/theqoo 존재, 2.0 미포팅 | robots/정책 준수 현황 재검증, 삭제글 처리. 사이트 추가/제외는 더 이상 결정 대기 아님 |
| 블로그 | 포함 | `aiporg/collect/blog.py`(1.0), 2.0 미포팅 | 검색 경로 중복 제거 연결, 광고·무관 게시물 판정 기준 |

각 어댑터 포팅/신규 구현 전에 공식 문서와 실제 키/권한으로 소규모 실 표본 수집을
먼저 실행해 반환 데이터 구조를 확인한다(§3.3, §11 M1). 이 실행은 코드 구현과
함께 진행하며 이번 계획 문서 작업에는 포함하지 않았다. **X·인스타그램은 1차
범위에서 완전히 제외됐으므로 M1 어댑터 목록에서 뺀다. 구글은 범위에 포함됐지만
수집기 자체는 아직 미구현 — M1에서 신규로 만들어야 한다.**

### 6. 먼저 구현할 최소 단위와 확장 순서

**1차 최소 단위** (단일 채널·단일 이슈로 전체 파이프라인을 끝까지 통과)

1. 로컬 테스트 환경을 실제로 통과시킨다(가상환경 구성, `tests_v2` 현재 상태
   재확인) — 선행 조건.
2. Narrative 출력 계약(2a)만 결정·구현하고 LLM 없이 기존 template 경로
   (`TemplateNarrativeService`)를 출력 schema에 연결한다.
3. 네이버 뉴스 collector에 페이지 순회만 추가(다른 채널 보류)해 월간 수집 1개
   채널을 실제로 완결한다.
4. mock LLM adapter(고정 응답)로 M3 흐름(저장·버전·재시도 방지)만 검증하고,
   실제 제공자 키 연결은 결정 이후로 미룬다.
5. Visualization 계약(2b) 중 집계값만 있으면 되는 가장 단순한 2개(VIS-02 채널
   도넛, VIS-07 TOP10 카드)만 구현해 M4 편집 UI의 "표시→승인" 흐름을 끝까지
   연결한다.
6. Streamlit UI는 8화면 전체가 아니라 "통계 검토 → 서술 편집 → 시각 자료 1~2종
   승인 → 보고서 미리보기 → 승인"만 먼저 연결한다.
7. HWPX는 표지+목차+요약 3쪽만 먼저 만들어 실제 한컴에서 연다(AT-15 축소판).

**확장 순서** (1차 통과 후)

- 채널: 다음 → 블로그/커뮤니티(1.0 포팅) → 유튜브(1.0 포팅) → 구글/X/인스타그램
  (접근성 검증 후).
- 이슈 수: 1개 → 4개(12쪽 기준) → 5개(페이지 확장).
- 시각 자료: VIS-02/07 → VIS-01,03,06,08 → VIS-04(이슈별 인포그래픽, 가장 복잡)
  → VIS-05(외부 조사, 자료 있을 때만) → VIS-09(추이, 선택).
- 출력: HWPX 3쪽 시제품 → 12쪽 전체 → DOCX/MD 동시 출력(M6) → API/CLI/월간
  복제(Phase 8).
- LLM: mock adapter → 실제 제공자 1개(비용 검토 후) → 실패 fallback/재시도 운영화.

각 확장 단계 전에 이전 단계의 unit/integration/회귀 테스트가 통과해야 한다
(AGENTS.md 9번).

### 7. 사용자 결정 목록 (요구사항 §13 통합 + 이번 세션 추가)

1. ~~기본 조사어(지역·기관·인물) 포함 여부~~ — **결정됨(2026-10-16, 3차): 미사용.**
   아래 "사용자 결정 반영" 절 참고.
2. ~~댓글 포함 여부/본문·댓글 지표 분리 방식~~ — **결정됨(2026-10-16, 3차): 포함.**
   아래 절 참고.
3. ~~커뮤니티 목록과 실제 접근 권한~~ — **결정됨(2026-10-16, 4차): 1.0의
   clien/dcinside/fmkorea/ruliweb/theqoo 목록을 그대로 쓴다.** 실제 접근
   권한·robots 준수 재검증은 M1 구현 시 필요(결정 자체는 완료).
4. 원본 HWPX/로고/표지 사진 확보 가능 여부(§13-4, 기존 미해결).
5. Narrative 출력·승인·시각 자산 버전 계약(§13-5) — 이번 세션 2절의 구체적
   제안안으로 진행할지, 세부안을 바꿀지 결정 필요. (미해결)
6. LLM 제공자: **부분 결정됨(2026-10-16, 3차) — API 직접 연결 방식 확정, 실제
   provider(GPT/Claude)·키는 추후 제공.** 비용 책임·예산 한도는 미해결.
7. ~~구글/X/인스타그램 수집을 1차 범위에 포함할지~~ — **결정됨(2026-10-16, 4차):
   구글 포함, X·인스타그램 제외(유료 접근 불가 판단).** 구글 수집기 자체는
   아직 미구현(M1).
8. ~~Streamlit UI 배치 위치와 실행 방식~~ — **결정됨(2026-10-16, 4차):
   `streamlit_app/console.py`, 로컬 전용, `streamlit run streamlit_app/console.py`.**
   아래 "2026-10-16 Streamlit 콘솔 MVP" 절 참고.
9. (신규) 1.0 유튜브/커뮤니티/블로그 수집기를 "포팅"할지 "재작성"할지. 포팅 시
   1.0 analyzer 로직을 분석 단계로 분리하는 작업을 M1에 포함할지 M2로 미룰지.
   (미해결)
10. ~~로컬 테스트 가상환경 구성~~ — **결정됨/확인됨(2026-10-16, 4차): Python
    3.12 venv(`.venv/`)로 `tests_v2`+`tests` 254개 전체 통과 확인.** 아래 절의
    정확한 명령어 참고. 시스템 기본 `/usr/bin/python3`(3.9.6)로는
    `matplotlib==3.11.0`이 설치되지 않아 동작하지 않는다 — Python 3.10+가
    필요하다.

## 2026-10-16 사용자 결정 반영 (3차): 월별 키워드 입력, 댓글 포함, 수집 진행 UI

사용자가 결정 목록 1·2·6을 확정하고 Streamlit 수집 화면의 구체 요구를 추가했다.
아래는 그 결정과, 기존 코드 계약(`app/schemas/{query,collection,document,common,project}.py`)
을 다시 확인해 **새 schema 없이 구현 가능한 범위**를 구분한 결과다.

### 결정 1: 고정 조사어 미사용 — 월별 키워드 리스트가 조사 범위 전체

지역·기관·인물 기본 조사어를 검색어에 자동으로 추가하지 않는다. 사용자가 매월
Streamlit에 입력하는 키워드 리스트가 그 달 조사 범위의 전부다(요구사항 §3.1의
"월별 키워드만 조사하면 보고서 범위도 해당 키워드로 한정" branch를 채택). 개수는
4~5개로 고정하지 않고 가변이다. 예시(2026년 9월, 사용자 제공, 실제 이번 달
키워드로 사용):

- 공공기관 충남 2차 이전, 내포신도시
- 충남 재정전략회의
- 인사청문특위 부적격판단 전격수용
- 삼성 디스플레이 67조 투자유치

**코드 영향:** `app/schemas/query.py`의 `SearchQuery.query: str`는 이미 자유 문자열
하나를 받는다. `app/schemas/project.py`의 `TargetSchema`(organization/primary_person/
region)는 유지하되 **검색어에 자동 병합하지 않고** 동명이인·타지역 혼동 방지용
맥락 정보로만 쓴다(요구사항 §3.1 두 번째 문단). Project 수준에 "이번 달 키워드
리스트"를 저장하는 별도 필드는 **신설하지 않는다** — 이미 존재하는
`QuerySetRepository.create(project_id, queries: list[SearchQuery])`(프로젝트의
query set을 통째로 교체하는 contract, `app/repositories/{collection,sqlalchemy}.py`에
이미 구현되어 있음을 2026-10-16 4차 세션에서 코드로 확인)가 정확히 이 저장소다.
Streamlit은 키워드 N개를 `SearchQuery` N개로 만들어 `QuerySetRepository.create()`
한 번으로 저장하고, 이후 `CollectionRun`은 각 키워드(query)×채널 조합마다
생성한다. (이전 개정에서 "CollectionRun.query 고유값 집합으로 암묵 표현"이라고
썼던 것은 기존 `QuerySetRepository`를 놓친 부정확한 서술이었다 — 이 절에서
정정한다.) 동의어/제외어 입력(요구사항 §3.1)은 1차 구현에 넣지 않고, 한 줄 =
검색어 1개로 단순화한다(필요해지면 별도 결정으로 확장).

### 결정 2: 댓글 포함 — 신규 schema 없이 metadata 컨벤션으로 구분

댓글을 포함해 수집한다. 신규 테이블/필드 대신 기존 `RawDocument.metadata:
dict[str, object]`(이미 감성 라벨을 `metadata["sentiment"]`로 저장하는 선례가
있음, `docs/aiporg2/analytics.md` 참고)에 아래 컨벤션으로 저장하는 것을 제안한다.

- `metadata["document_type"]`: `"article"`(기본) 또는 `"comment"`.
- `metadata["parent_document_id"]`: 댓글일 때 부모 글의 `document_id`(문자열).
- `metadata["is_requote"]`: 재게시 중 실질적 새 의견이 있는 인용 게시물 구분(선택).

`app/analytics/service.py`의 언급량 집계는 `document_type == "article"`만 기본
분모로 쓰고, 댓글 집계는 별도 지표로 분리한다(요구사항 §4.2 "댓글 포함 지표는
별도 이름·분모"). 이 컨벤션은 M0 결정 대상이지만 **새 Pydantic 필드가 아니라
기존 `metadata` dict 안의 키 값 약속이므로 AGENTS.md 1번 규칙상 schema 추가가
아니다** — 다만 이 컨벤션 자체는 narrative-design.md와 같은 절차로 설계 문서에
명시하고 결정한 뒤 collector/analyzer 양쪽에 일관되게 구현한다.

### 결정 6(부분): LLM은 API 직접 연결, 키는 추후 제공

제공자 CLI 구독이 아니라 **API 직접 호출** 방식으로 확정한다. 실제 API 키는
나중에 전달된다. `app/narrative/llm_adapter.py`(M3, 아직 미작성)는 키가 없어도
동작해야 한다: 환경변수/Streamlit secrets에서 키를 읽고, 키가 없으면 기존
`TemplateNarrativeService`로 자동 fallback한다. GPT와 Claude 중 어느 쪽을
기본으로 할지는 아직 미정이므로 provider를 설정값으로 선택 가능하게 만들고
(OpenAI 호환 요청 형태와 Anthropic 요청 형태를 어댑터 내부에서 분기), 특정
제공자에 종속된 코드를 narrative 계층 밖에 두지 않는다(AGENTS.md 4,5번 규칙과
동일한 경계).

### 신규 요구: Streamlit 수집 설정·진행 화면 구체 명세

사용자가 요구한 화면 동작을 §8 "수집 설정·실행"/"수집 결과 검토" 화면에 아래처럼
구체화한다.

1. **입력:** 조사 기간(시작일/종료일, 예: 2026-09-01~2026-09-30 — 기존
   `AnalysisPeriodSchema(start: date, end: date)` 그대로 사용 가능), 키워드
   리스트(여러 줄 텍스트 입력, 줄당 키워드 1개, 개수 가변).
2. **실행:** 입력 제출 시 Streamlit이 `app/collection/service.py`의 collection
   orchestration을 키워드×채널 조합으로 호출해 `CollectionRun`을 생성한다.
3. **진행 상황 화면:** 기존 `CollectionRun`(`status`, `started_at`, `completed_at`,
   `documents_found`, `documents_saved`, `error_count`)을 프로젝트 단위로 조회해
   키워드(`query`)×채널(`channel`)별 실행 상태(진행중/완료/실패)를 표로 보여준다.
   **새 schema 없이 기존 repository 조회만으로 구현 가능.**
4. **채널/커뮤니티별 확보 건수:** 기존 `RawDocument.source`(자유 문자열, 예:
   "클리앙", "디시인사이드", "네이버뉴스")로 그룹핑하면 "어느 커뮤니티에서 몇 건"
   요구를 **새 schema 없이** 충족할 수 있다. **정정(2026-10-16 4차, 실제 구현
   결과): 별도 repository 메서드를 core에 추가하지 않고도 가능했다.** 이미 있는
   `DocumentRepository.list_raw_by_collection_run(project_id, run_id)`을 추적
   중인 run마다 호출해 `source`로 client-side 집계하면 된다 — 아래 "Streamlit
   콘솔 MVP" 절 참고.
5. 위 3·4번은 "대략적 건수"이면 충분하다고 사용자가 명시했으므로, 1차 구현은
   polling 기반 단순 집계로 충분하고 실시간 push(WebSocket 등)는 범위에서
   제외한다.

**M1/M4 파일 작업에 반영:** `app/collection/service.py`에 키워드 리스트 → 다중
`SearchQuery` fan-out 추가(현재는 `streamlit_app/console.py`가 UI 레이어에서
직접 fan-out함 — 아래 참고), Streamlit "수집 설정·실행"/"수집 결과 검토" 화면.
이 작업은 신규 schema가 필요 없으므로 M0 계약 결정(Narrative/Visualization/Report)과
독립적으로 바로 M1에서 착수할 수 있다.

## 2026-10-16 Streamlit 콘솔 MVP와 테스트 환경 확인 (4차)

사용자가 X·인스타그램 제외, 구글 포함, 커뮤니티 목록(1.0 그대로) 결정을 추가로
확정했고, "Streamlit을 실행할 수 있는 명령어"와 "프로젝트 자체가 Streamlit
기반으로 실행되도록" 요청했다. 이번에는 계획 문서화에 더해 **실제로 동작하는
코드를 작성·검증**했다(이전 3번의 세션은 문서만 변경했다).

### 테스트 환경 확인 (결정 목록 10번 해결)

시스템 `/usr/bin/python3`(3.9.6)에는 `matplotlib==3.11.0`이 설치되지 않는다
(3.10+ 필요). Homebrew의 `/opt/homebrew/bin/python3.12`로 저장소 루트에 `.venv`를
만들어 확인했다.

```bash
# 최초 1회: 가상환경 생성 + 의존성 설치
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# 테스트 (실제로 실행해 확인함)
.venv/bin/python -m pytest tests_v2 tests -q
# -> 254 passed (narrative-design.md의 2026-09-23 "254 passed" 기록과 일치)
```

`.venv/`와 `aiporg2.db`는 `.gitignore`에 추가했다.

### Streamlit 콘솔 MVP (결정 목록 8번 해결)

`streamlit_app/console.py` 신규 작성. **주의: 파일명을 `app.py`로 하면 안 된다**
— Streamlit이 스크립트 디렉터리를 `sys.path`에 넣는데, 그 디렉터리에 `app.py`가
있으면 `from app.collection...` import가 저장소 루트의 `app/` 패키지 대신 그
스크립트 파일 자신을 "app"으로 잘못 찾아 `ModuleNotFoundError`가 난다(실제로
`app.py`로 처음 만들었다가 이 오류를 재현하고 `console.py`로 바꿔 해결함 — 이름이
`app`과 충돌하는 어떤 파일명도 같은 문제를 일으킨다).

**실행 명령어:**

```bash
.venv/bin/streamlit run streamlit_app/console.py
```

최초 실행 시 `alembic upgrade head`를 코드에서 자동 호출해 `aiporg2.db`를
만든다(idempotent라 매 실행마다 호출해도 안전). 네이버/다음 API 키는
`.env`(또는 쉘 환경변수)의 `AIPORG2_NAVER_CLIENT_ID`, `AIPORG2_NAVER_CLIENT_SECRET`,
`AIPORG2_KAKAO_REST_API_KEY`로 주입한다 — 없으면 해당 채널 체크박스가 비활성화된
채로 "자격증명 없음"이라고 표시된다.

**구현 범위 (8화면 중 3개는 실제 동작, 나머지는 명시적 미구현 안내):**

1. **월별 프로젝트** — `ProjectRepository.create`로 실제 생성. 기관/인물/지역은
   맥락 정보로만 저장하고 검색어에 합치지 않는다.
2. **수집 설정·실행** — 기간 + 키워드 리스트(여러 줄) 입력, 네이버/다음 체크박스
   (구현됨, 자격증명 있으면 실행 가능), 구글/커뮤니티/유튜브는 "범위 포함,
   수집기 미구현" 배지로 비활성 표시. 제출 시 `QuerySetRepository.create()`로
   키워드를 저장하고, 생성된 `Query.id`를 조회해 키워드×채널마다
   `CollectionService.collect()`를 실행한다.
3. **수집 결과 검토** — 추적 중인 run마다 `CollectionRunRepository.get()`으로
   상태/건수를 보여주고, `DocumentRepository.list_raw_by_collection_run()`을
   `source`로 모아 막대그래프로 "어느 채널에서 몇 건"을 보여준다.
4. **통계·이슈 검토** — 정제·Evidence 파이프라인이 이 화면과 아직 연결 안 돼
   있음을 명시하고 멈춘다(가짜 숫자를 보여주지 않음).
5~8. **서술 편집/시각 자료 편집·승인/보고서 미리보기/출력·이력** — 각각 왜
   아직 안 되는지(M0/M3/M5 의존)를 명시한 "미구현" 패널.

**알려진 한계(코드로 확인, 다음에 해결할 것):**

- `ProjectRepository`와 `CollectionRunRepository`에 "프로젝트 전체 목록"·
  "프로젝트의 전체 run 목록" 조회 메서드가 없다. 지금은 Streamlit
  `st.session_state`로 같은 브라우저 세션 동안만 생성한 프로젝트/실행한 run을
  기억한다 — 앱을 재시작하면 세션 상태가 사라지고, 기존 프로젝트는 UUID를 직접
  입력해야 다시 불러올 수 있다. §8 요구("새로고침·재시작 후 유지")를 완전히
  만족하려면 이 조회 메서드 추가가 필요하다(신규 schema 아닌 조회 메서드이므로
  M1/M4 범위에서 추가 가능).
- "수집 실행"은 `CollectionService`만 호출하고 `CollectionToEvidenceWorkflow`
  (정제→중복제거→Evidence)는 아직 연결하지 않았다. 이 workflow는 project당
  한 번의 query/run만 받는 구조라 키워드 N개 fan-out과 바로 맞지 않는다 — 여러
  키워드를 Evidence까지 연결하는 orchestration은 M1에서 별도로 설계해야 한다
  (이번 세션에서 임의로 만들지 않았다).

**검증 방법:** `streamlit.testing.v1.AppTest`로 8개 화면 전환, 프로젝트 생성
폼 제출, 가짜 collector로 수집→조회 경로를 실행해 예외 없이 동작하고 DB에 실제
행이 쓰이는 것을 확인했다(브라우저 수동 테스트는 하지 않음). 실 네이버/다음
API 키로의 실제 네트워크 호출은 이번에 하지 않았다.

## 2026-10-16 수집 정확도와 파이프라인 연결 (5차)

사용자 요청: "최대한 정확도 올리는 수집 방향으로. 지금 있는 파이프라인도 한번
점검해도 좋고, 요구사항에 맞는 데이터 수집이 잘 되는지." 이번 세션은 4차에서
만든 Streamlit 콘솔을 실제 `streamlit run`으로 실행했을 때 난 import 오류를
먼저 고치고, 코드를 점검해 발견한 정확도 문제를 수정했다.

**실행 버그 수정:** 실제 `streamlit run streamlit_app/console.py`는
`ModuleNotFoundError: No module named 'app'`로 실패했다. 4차의 `AppTest` 기반
검증은 호출 시점의 cwd도 `sys.path`에 넣어줘서 우연히 통과했지만, 실제
`streamlit run`은 스크립트 자신의 디렉터리만 넣는다. `streamlit_app/console.py`
맨 위에 `sys.path.insert(0, REPO_ROOT)`를 명시적으로 추가해 cwd와 무관하게
동작하도록 고치고, cwd를 `/tmp`로 바꾼 채로 재현·검증했다.

**파이프라인 점검 결과:**
- `app/collectors/naver_news.py`가 `start=1, display=100` 고정 단일 요청만 해서
  바쁜 키워드의 월간 기사를 최대 100건에서 잘라내고 있었다 — 가장 큰 정확도
  문제로 보고 수정했다(아래).
- `app/cleaning/service.py`(URL 정규화: 트래킹 파라미터 제거, scheme/host
  소문자화, 기본 포트 제거)와 `app/dedup/service.py`(URL exact → 제목 exact →
  본문 해시 exact, 3단계)는 검토 결과 설계대로 올바르게 동작해 변경하지 않았다.
- `app/collectors/daum_news.py`는 4차까지의 서술과 달리 이미 `meta.is_end`까지
  전체 페이징하고 있었다(정정, 위 섹션들에도 반영함).

**수정 1 — naver 페이지네이션:** `app/collectors/naver_news.py`의 `search()`를
Naver API 한도(`start<=1000`)까지 페이징하도록 바꿨다. unit test 2개 추가
(`tests_v2/unit/test_naver_news_collector.py`): 여러 페이지 순회, 1000건
상한에서 정지.

**수정 2 — `MultiQueryCollectionToEvidenceWorkflow` 신규
(`app/workflows/multi_query_collection_to_evidence.py`):** 기존
`CollectionToEvidenceWorkflow`는 project당 query 1개만 받고 `WorkflowState`를
한 번만 전진시키는 구조다(`app/core/state_machine.py`의 각 상태는 정확히 한
번만 다음 상태로 전진 가능). 이걸 키워드 수만큼 루프 돌리면 두 번째 키워드부터
`InvalidStateTransitionError`가 난다. 새 workflow는 요청 N개를 전부 수집한 뒤
`COLLECTION_RUNNING`/`COLLECTION_COMPLETED`를 한 번만 거치고, **그 배치에서
수집된 raw document 전체의 합집합**에 정제·중복제거·Evidence를 한 번에
적용한다 — 이게 §3.2 "네이버와 구글에서 같은 기사를 발견해도 기사 한 건" 요구의
실제 구현이다(같은 URL이 다른 키워드에서도 발견되면 `upsert_raw`가
canonical_url 기준으로 같은 행에 덮어써서 문서 수가 늘지 않고, 남는 제목/본문
중복은 `DeduplicationService`가 추가로 잡는다). 기존 `CollectionToEvidenceWorkflow`
와 똑같이 **project당 한 번만** `QUERIES_READY → EVIDENCE_COMPLETED`를 거치는
제약은 그대로 유지했다 — 재수집하려면 새 프로젝트가 필요하다(기존 설계와
동일한 제약을 N개로 확장한 것일 뿐, 새로운 제약을 만들지 않았다).

unit test 3개(빈 요청 거부, `QUERIES_READY` 아닌 상태 거부, 키워드 하나 실패해도
나머지는 진행해 `EVIDENCE_COMPLETED`까지 도달) + 통합 테스트 1개
(`tests_v2/integration/test_multi_query_collection_to_evidence_workflow.py`:
두 키워드에 같은 URL이 섞여 있어도 canonical 문서 3건·Evidence 3건으로 정확히
collapse되는 것을 실제 SQLite로 검증)를 추가했다.

**수정 3 — repository 조회 메서드:** `ProjectRepository.list()`,
`CollectionRunRepository.list_by_project()`(둘 다 신규 schema 아닌 조회
메서드, `app/repositories/{project,collection,sqlalchemy}.py`). Streamlit
콘솔의 "1. 월별 프로젝트"/"3. 수집 결과 검토"가 세션이 아니라 DB에서 직접
읽도록 연결해, 앱 재시작 후에도 프로젝트/실행 이력이 남는다(4차의 알려진
한계 해결).

**Streamlit 콘솔 연결:** "2. 수집 설정·실행"이 `MultiQueryCollectionToEvidenceWorkflow`
를 호출하도록 바꿨다. 이미 수집을 실행한 프로젝트는 폼을 숨기고 새 프로젝트를
만들라는 안내만 보여준다. "4. 통계·이슈 검토"는 더 이상 "미연결" 안내뿐이
아니라 canonical 문서 수·Evidence 수·문서 목록을 실제로 보여준다(전체
`AnalyticsSnapshot` 집계는 여전히 M2 대상).

**실제 실행 검증:** 가짜 네이버/다음 collector로 Streamlit 콘솔의
`_run_collection`을 직접 호출해 프로젝트 생성 → 키워드 2개×채널 2개 수집 →
DB 상태(`EVIDENCE_COMPLETED`, CollectionRun 4건, Document 4건, Evidence
2건 — 제목 중복 2건이 올바르게 걸러짐)를 sqlite3로 직접 확인했고, `AppTest`로
화면 1·3·4가 그 데이터를 정확히 보여주는 것도 확인했다. 이 과정에서 또 다른
버그를 발견·수정함: `_run_collection`을 고치면서 `CREATED → QUERIES_READY`
전진 호출을 빠뜨렸는데, 새 workflow가 `QUERIES_READY`를 요구해서 조용히
`InvalidStateTransitionError`로 실패하고 있었다 — 되돌려 고쳤다.

**완료 기준 확인:** `tests_v2`+`tests` **260 passed**(254 + naver 2 +
multi-query unit 3 + 통합 1). 실 네이버/다음 API 네트워크 호출은 하지 않았다
(키 미설정 상태로 검증). 신규 schema·DB 테이블·workflow state는 추가하지
않았다 — repository 조회 메서드와 기존 서비스를 재사용하는 새 orchestration
class만 추가했다.

## 2026-10-16 유튜브 collector, Narrative 출력 계약, Gemini 어댑터 (7·8차)

사용자가 "유튜브 Data API v3와 Gemini를 무료 한도 내에서 쓰고 싶다"고
요청했다. 유튜브는 바로 구현했고(7차), Gemini는 narrative 출력 계약이 미결정
상태였어서 먼저 "최소 계약으로 narrative 저장 구조만 결정하고 구현할지"
사용자에게 물었다 — 그렇게 하기로 했고 모델은 `gemini-2.0-flash`로 정했다(8차).

### 7차: `app/collectors/youtube.py`

YouTube Data API v3 `search.list`(키워드→영상 ID, 기본 1페이지/최대 50건 —
무료 일일 10,000 유닛 중 100유닛/호출로 가장 비싼 호출이라 기본을 보수적으로
잡음, `max_pages`로 조정 가능)와 `videos.list`(영상별 제목/설명/통계,
1유닛/호출)를 호출한다. `aiporg/youtube/collector.py`(1.0)를 참고했지만
그대로 재사용하지 않고 2.0 `CollectorProtocol`(search/fetch 분리)에 맞춰
새로 작성했다 — 1.0은 project당 여러 키워드를 모아 `videos.list`를 50개씩
배치 호출하지만, 2.0은 키워드별로 `search()`를 따로 호출하는 구조라 그
최적화는 옮기지 못했다(그래도 무료 한도 안에는 충분히 든다). 댓글
(`commentThreads.list`)은 구현하지 않았다. `Settings.youtube_api_key`/
`AIPORG2_YOUTUBE_API_KEY` 추가, Streamlit `PROVIDER_CHANNELS`에 연결.

연결하며 기존 버그 하나를 발견·수정함: `streamlit_app/console.py`가 모든
provider의 `SearchQuery.channels`를 `ChannelType.NEWS`로 하드코딩하고
있었다(naver/daum만 있을 때는 우연히 맞았음). `PROVIDER_CHANNELS` 매핑으로
고치고 DB에 `channel='VIDEO'`로 저장되는 것까지 확인했다.

unit test 10개(`tests_v2/unit/test_youtube_collector.py`).

### 8차: Narrative 출력 계약 결정·구현 + `GeminiNarrativeAdapter`

`docs/aiporg2/narrative-design.md`의 2026-09-23 권장안(신규 테이블 없이 기존
`narratives.context` JSON에 구분 가능한 envelope로 저장)을 최종 채택해
구현했다. 상세는 그 문서와 HANDOFF.md의 "8차" 절 참고. 요약:

- `app/schemas/narrative.py`에 `NarrativeSentenceSchema`/
  `NarrativeGenerationSchema`/`NarrativeOutputSchema`를 **추가만** 함.
  `NarrativeContext`, `ReportSchema.context: NarrativeContext` 등 기존 계약은
  그대로 유지.
- `NarrativeRepository.save_output`/`get_latest_output` 추가. 출력 row는
  `context` JSON에 `{"kind": "narrative_output", "data": {...}}`로 저장,
  입력 row는 기존 그대로(`NarrativeContext`가 `extra="forbid"`라 입력 row에는
  구조적으로 `kind` 키가 있을 수 없다는 점으로 구분 — 신규 컬럼 없음). 기존
  `get_latest()`가 출력 row를 건너뛰도록 고쳐서, 출력을 저장해도 기존 입력
  조회 결과가 그대로임을 테스트로 확인.
- 테스트 중 발견: `get_latest_output()`을 DB `created_at` 정렬로 처음 짰더니
  SQLite `CURRENT_TIMESTAMP`의 1초 해상도 때문에 같은 초 안의 재생성 순서가
  비결정적이었다 — 각 출력이 자기 payload에 갖는 고해상도 `run.created_at`
  으로 비교하도록 고쳤다.
- `app/narrative/llm_adapter.py`의 `GeminiNarrativeAdapter`: Context+Analytics+
  Evidence로 프롬프트를 만들어 Gemini `generateContent`(JSON 응답 모드)를
  호출하고, **모델의 인용을 그대로 믿지 않는다** — 각 문장의 fact/evidence/
  document id와 analytics_paths가 실제 입력에 있는지 검사해서 근거 없는
  문장은 버리고, 전부 버려지면 `NarrativeGenerationError`로 실패한다.
- 의도적으로 안 한 것: draft orchestration service(호출+fallback+저장을
  묶는 상위 서비스), Streamlit "5. 서술 편집" 연결. 후자는 더 근본적인
  이유가 있다 — 이 콘솔에 Issue 확정과 AnalyticsSnapshot 생성이 전혀
  연결돼 있지 않아 `NarrativeContext` 입력 자체를 만들 수 없다(다음 행동
  1순위로 HANDOFF에 기록함).

unit test 15개(narrative output schema 6, Gemini adapter 9) + repository
테스트 보강 1개. `tests_v2`+`tests` **282 passed**(270 + 12). 실제 Gemini
API 네트워크 호출은 하지 않았다(가짜 transport로 검증).

## 1. 목표

현재 구현된 AIPORG 2.0의 schema, SQLAlchemy model, repository protocol,
workflow state machine과 기초 서비스를 실제 실행 가능한 파이프라인으로 완성한다.

최종 실행 흐름은 아래와 같다.

```text
Project 생성
  -> Query 준비
  -> Collection
  -> Cleaning / Deduplication
  -> Evidence / Fact 검증
  -> Issue Discovery
  -> Analytics
  -> Narrative
  -> Visualization
  -> Report
```

완료 기준은 각 단계의 결과가 repository를 통해 저장되고, workflow state와
versioned run 정보가 함께 갱신되며, 동일한 fixture 입력으로 최종 보고서까지
재현 가능한 것이다.

## 2. 구현 원칙

1. 기존 Pydantic model과 필드 이름을 변경하지 않는다.
2. 요구사항에 없는 schema를 추가하지 않는다. 필요한 표현이 기존 schema로
   불가능하면 먼저 설계 문서에 불일치를 기록하고 별도 결정을 받는다.
3. 모든 DB write는 repository 구현을 통해서만 수행한다.
4. Collector는 수집과 원문 변환만 담당하며 LLM을 호출하지 않는다.
5. Analyzer는 저장된 문서와 evidence만 사용하며 웹 요청을 하지 않는다.
6. Narrative와 Writer는 검증된 fact를 표현하며 새로운 fact나 수치를 만들지 않는다.
7. 모든 module 변경에는 해당 module의 unit test를 함께 추가한다.
8. 각 단계의 integration test가 실패하면 다음 단계 구현을 시작하지 않는다.
9. 기존 `aiporg/` 1.0 경로는 회귀 테스트 대상으로 유지한다.

## 3. 현재 기준선

구현됨:

- core enum, 설정, 로깅, workflow state machine
- Pydantic contract와 SQLAlchemy metadata
- Alembic Phase 0 baseline
- repository protocol
- 네이버 뉴스 및 다음 뉴스 collector와 HTTP transport
- collection orchestration
- cleaning, 3단계 deterministic deduplication
- evidence 발췌, fact 상태 검증
- entity 기반 issue candidate discovery
- 채널별 문서 수 analytics

미구현 또는 불완전:

- 테스트 의존성이 설치된 재현 가능한 개발 환경
- SQLAlchemy session과 repository concrete implementation
- 실제 Alembic upgrade 검증
- 단계별 application service와 전체 workflow orchestration
- fact 추출 및 evidence 내용과 claim의 정합성 검증
- issue 확정, 상세 분석, 종합 analytics
- grounded narrative, visualization, report engine
- 2.0 API/CLI와 운영 관측성
- 전체 integration 및 1.0 회귀 검증

## 4. 단계별 구현 계획

### Phase 1. 실행 기준선과 테스트 게이트 확립

목적: 이후 기능 구현 여부를 판단할 수 있는 신뢰 가능한 테스트 환경을 만든다.

작업:

- 개발·테스트 의존성을 명시하고 한 명령으로 설치 가능하게 한다.
- `tests_v2/contracts`, `tests_v2/unit`, 기존 `tests` 실행 명령을 고정한다.
- SQLite 임시 DB에 Alembic baseline을 실제 적용하고 downgrade하는 integration test를 추가한다.
- 빈 DB에서 metadata와 migration 결과가 일치하는지 검증한다.
- 1.0 테스트 결과를 회귀 기준선으로 기록한다.

완료 조건:

- contract/unit test 전체 통과
- Alembic upgrade/downgrade integration test 통과
- 기존 1.0 테스트 전체 통과

게이트: 하나라도 실패하면 Phase 2를 시작하지 않는다.

### Phase 2. Persistence 구현

목적: protocol로만 존재하는 repository를 실제 DB 동작으로 완성한다.

작업:

- engine/session factory와 transaction boundary를 구현한다.
- Project, QuerySet, CollectionRun, Document repository를 우선 구현한다.
- DuplicateCluster, Evidence, Fact, Issue repository를 구현한다.
- Analytics, Narrative, Visualization, Report repository를 구현한다.
- schema와 ORM 사이의 명시적 mapper를 둔다.
- project 범위 unique constraint, upsert, rollback, not-found, conflict 처리를 검증한다.

테스트:

- repository별 CRUD 및 project isolation unit test
- transaction rollback과 unique conflict test
- 실제 SQLite repository integration test
- migration DB를 사용한 repository 전체 smoke test

완료 조건:

- service가 ORM이나 session에 직접 접근하지 않음
- 모든 repository contract가 concrete implementation으로 충족됨
- Phase 2 integration test 전체 통과

### Phase 3. Collection에서 Evidence까지 연결

목적: 검색 결과를 정제된 고유 문서와 evidence로 저장하는 첫 수직 흐름을 완성한다.

작업:

- query와 collection run 생성 서비스를 연결한다.
- collector 결과를 raw document repository에 upsert한다.
- cleaning 결과와 canonical URL을 저장한다.
- dedup cluster와 canonical document 선택 결과를 저장한다.
- canonical 문서에서 evidence를 만들고 저장한다.
- 성공한 단계에서만 workflow state를 전진시킨다.
- 단계별 `run_id`, `input_version`, `output_version`을 기록한다.
- 실패 시 run 상태와 오류를 보존하고 project state는 마지막 성공 단계에 유지한다.

테스트:

- collector는 repository 외 DB write를 하지 않는지 검증
- 동일 URL 재수집 시 중복 저장 방지
- 부분 fetch 실패와 재실행 복구
- collection -> cleaning -> dedup -> evidence integration fixture

완료 조건:

- fixture query 하나로 `EVIDENCE_COMPLETED`까지 재현 가능
- 네트워크 없이 integration fixture가 반복 실행됨

### Phase 4. Fact와 Issue 엔진 완성

목적: 문서 기반 claim을 추적 가능한 fact와 issue로 변환한다.

작업:

- 기존 FactSchema 범위에서 deterministic fact 후보 추출기를 구현한다.
- claim의 모든 numeric token이 연결된 evidence에 존재하는지 검증한다.
- source count를 repository의 실제 고유 출처에서 계산한다.
- 공식 출처 판정은 설정된 source policy로 제한한다.
- fact 상태와 confidence를 검증 결과에서 계산한다.
- entity signature 후보를 issue로 확정하는 규칙을 구현한다.
- issue-fact 관계와 source/channel 통계를 저장한다.
- unsupported 또는 uncertain fact가 narrative 입력에 섞이지 않도록 조회 경계를 둔다.

테스트:

- evidence에 없는 숫자 거부
- source count 위조 방지
- 근거 없는 claim 거부
- 동일 fact 중복 처리
- evidence -> fact -> issue integration fixture

완료 조건:

- 각 issue에서 원문 document와 evidence까지 역추적 가능
- `ISSUES_COMPLETED` 단계 integration test 통과

### Phase 5. Analytics 엔진 확장

목적: 보고서가 필요한 모든 수치를 검증된 저장 데이터에서 계산한다.

작업:

- 기간·채널별 unique document 언급량을 계산한다.
- 감성 분포, 키워드 빈도, 일별 추이, 비교기간 증감을 구현한다.
- issue별 문서·출처·채널 분포를 계산한다.
- 비교기간이 없으면 숫자 대신 기존 contract가 허용하는 명시적 상태를 사용한다.
- analytics snapshot에 입력 version과 계산 기준을 기록한다.
- dedup 전후 데이터가 통계에서 혼용되지 않도록 canonical 조회를 고정한다.

테스트:

- 모든 수치의 입력 document/evidence 추적성
- 0건, 단일 채널, 비교기간 없음, 부분 감성 라벨 케이스
- 중복 문서가 언급량에 재반영되지 않는지 검증
- issues -> analytics integration fixture

완료 조건:

- 보고서용 수치가 임의 상수 없이 snapshot에서 제공됨
- `ANALYTICS_COMPLETED` integration test 통과

### Phase 6. Grounded Narrative 구현

목적: 검증된 fact와 analytics만 사용해 공공기관 보고서 문장을 만든다.

작업:

- 먼저 deterministic template narrative를 구현한다.
- NarrativeContext에서 허용한 fact와 analytics만 입력한다.
- 출력 문장의 숫자와 고유명사가 입력에 존재하는지 사후 검증한다.
- source mapping을 저장해 문장별 근거를 추적한다.
- LLM adapter가 필요하면 별도 narrative 계층에만 추가하고 collector와 analyzer에서는 사용하지 않는다.
- LLM 실패 시 검증 가능한 template 결과로 fallback한다.

테스트:

- 입력에 없는 숫자·fact 차단
- empty/sparse context 처리
- 같은 입력의 template 출력 재현성
- narrative와 source mapping integration test

완료 조건:

- 모든 narrative 문장이 fact 또는 analytics snapshot에 연결됨
- `NARRATIVE_COMPLETED` integration test 통과

### Phase 7. Visualization과 Report 구현

목적: 저장된 analytics와 narrative를 최종 산출물로 렌더링한다.

작업:

- Visualization engine은 analytics snapshot에서만 차트 데이터를 읽는다.
- Report engine은 narrative, visualization, source mapping을 조립한다.
- 1차 출력은 DOCX로 고정하고 이후 필요 시 HTML/PDF를 추가한다.
- Writer는 계산이나 fact 생성을 하지 않고 전달받은 값만 표현한다.
- 빈 섹션, sparse data, 한글 줄바꿈, 표 overflow를 처리한다.
- 생성 artifact와 checksum, version을 Report repository에 저장한다.

테스트:

- 필수 장과 섹션 순서
- 표와 차트의 값이 analytics와 일치하는지 검증
- evidence/source appendix 존재
- sparse fixture 렌더링
- DOCX render smoke test와 최종 pipeline integration test

완료 조건:

- fixture project가 `REPORT_COMPLETED`까지 실행됨
- 최종 보고서의 모든 수치와 서술 근거를 역추적할 수 있음

### Phase 8. API/CLI와 운영 준비

목적: 사용자가 프로젝트를 생성하고 실행 상태와 결과를 조회할 수 있게 한다.

작업:

- 2.0 전용 CLI 또는 FastAPI application entrypoint를 구현한다.
- project 생성, 실행 시작, 상태 조회, 최신 report 조회를 제공한다.
- 동일 단계 재실행과 downstream stale 처리를 구현한다.
- structured logging에 project_id, run_id, stage를 포함한다.
- credential과 환경 설정 검증, timeout, retry, 실패 상태를 정리한다.
- 1.0과 import, DB, CLI 경로가 충돌하지 않도록 유지한다.

테스트:

- API/CLI happy path와 잘못된 상태 전이
- 단계 재실행과 stale artifact 처리
- 실행 실패 후 재개
- 1.0 전체 회귀 테스트
- 2.0 end-to-end fixture test

완료 조건:

- 새 환경에서 설치, migration, 실행, 보고서 생성 절차가 문서대로 재현됨
- 전체 unit/contract/integration/regression test 통과

## 5. 작업 순서와 예상 단위

권장 작업 묶음은 아래와 같다. 기간은 인력과 리뷰 속도에 따라 조정한다.

| 순서 | 작업 묶음 | 예상 단위 | 핵심 산출물 |
|---|---|---:|---|
| 1 | 테스트 기반선 | 1~2일 | 재현 가능한 test command, migration integration |
| 2 | Persistence | 3~5일 | concrete repositories, transaction tests |
| 3 | Collection 수직 흐름 | 3~4일 | evidence까지 실행되는 workflow |
| 4 | Fact/Issue | 4~6일 | evidence-backed fact와 issue |
| 5 | Analytics | 3~5일 | versioned analytics snapshot |
| 6 | Narrative | 3~5일 | grounded deterministic narrative |
| 7 | Visualization/Report | 4~6일 | DOCX artifact와 source appendix |
| 8 | API/CLI/운영 | 3~5일 | 사용자 실행 경로와 재실행 지원 |

총 예상은 한 명 기준 약 24~38 개발일이다. 외부 LLM 품질 튜닝, PDF 픽셀 정합성,
추가 collector는 이 추정에서 제외한다.

## 6. 우선 구현 백로그

첫 번째 구현 사이클은 다음 순서로 제한한다.

1. 테스트 의존성 및 실행 명령 고정
2. 실제 Alembic upgrade/downgrade integration test
3. session/transaction factory
4. ProjectRepository 구현과 테스트
5. CollectionRunRepository 구현과 테스트
6. DocumentRepository 구현과 upsert integration test
7. 전체 Phase 2 persistence gate 실행

이 사이클이 통과하기 전에는 fact, narrative, report 기능을 추가하지 않는다.

## 7. 최종 수용 기준

- 기존 schema와 Pydantic model 이름이 유지된다.
- DB write가 repository 구현 내부로 제한된다.
- collector에 LLM 호출이 없고 analyzer에 웹 요청이 없다.
- 모든 numeric value가 evidence 또는 analytics 입력으로 추적된다.
- writer가 새로운 fact를 생성하지 않는다.
- 각 module 변경에 unit test가 있다.
- 각 phase의 integration gate를 통과한 이력이 있다.
- 동일 fixture 입력으로 동일한 핵심 분석 결과와 보고서를 생성한다.
- AIPORG 1.0 전체 회귀 테스트가 통과한다.

## 8. 진행 기록

### 2026-09-08: Phase 1, Phase 2 완료

- 개발·테스트 의존성을 `requirements-dev.txt`에 고정함
- SQLite Alembic upgrade/downgrade runtime integration test 추가
- SQLAlchemy session factory, SQLite foreign key 활성화, commit/rollback unit of work 추가
- 모든 기존 repository protocol의 SQLAlchemy 구현 추가
- project 격리, query set, collection run, document upsert/cleaning 저장 검증
- evidence, fact, numeric fact, issue, analytics, narrative, visualization, report round-trip 검증
- migration으로 생성한 실제 DB에서 repository write/read smoke test 검증
- AIPORG 2.0 및 기존 1.0 전체 테스트: `193 passed`

### 2026-09-15: Phase 3 완료

- collection run ID를 raw document 저장 경로에 연결함
- collection run별 raw document 조회 repository contract와 구현 추가
- project workflow 조회 및 단일 단계 전진 repository contract와 구현 추가
- Collection, Cleaning, Deduplication, Evidence service를 하나의 application workflow로 연결함
- 성공한 collection만 workflow state를 전진하도록 처리함
- 검색 실패 시 failed collection run을 보존하고 project는 `QUERIES_READY`에 유지함
- title/body 중복 fixture에서 canonical document만 evidence로 생성함
- 검색 실패 후 새 run으로 재시도해 `EVIDENCE_COMPLETED`에 도달하는 흐름 검증
- AIPORG 2.0 및 기존 1.0 전체 테스트: `196 passed`

현재 Document, Evidence contract에는 `input_version`과 `output_version` 필드가 없다.
AGENTS.md의 schema 동결 규칙에 따라 Phase 3에서 임의 필드를 추가하지 않았으며,
단계별 version lineage는 기존 contract를 변경하는 명시적 설계 결정 전까지 보류한다.

### 2026-09-17: Phase 4 완료

- Evidence 원문의 첫 문장을 그대로 사용하는 deterministic fact extractor 추가
- fact ID를 project, event date, claim, entity 조합으로 결정론적으로 생성함
- source count를 연결 문서의 실제 고유 출처에서 계산함
- 설정으로 전달된 공식 출처 또는 복수 독립 출처에 따라 fact 상태를 검증함
- NumericFact 값이 연결된 Evidence 본문에 실제 존재하는지 검증함
- 검증된 fact claim만 반복 사용하여 issue detail을 확정함
- Evidence→Fact→Issue application workflow와 repository 조회 경로 추가
- document, evidence, fact, issue의 역추적 가능한 연결을 integration test로 검증함
- 성공 시 project workflow가 `ISSUES_COMPLETED`로 전진함
- AIPORG 2.0 및 기존 1.0 전체 테스트: `203 passed`

### 2026-09-21: Phase 5 완료

- 정제 완료 문서에서 저장된 duplicate member를 제외하는 canonical 조회 경로 추가
- 분석기간의 고유 문서 수, 채널·출처 분포, 일별 추이와 문서별 근거 ID 저장
- 기존 metadata 감성 라벨의 분포와 미분류 건수 집계; 감성 라벨 자동 생성은 하지 않음
- 제목·본문의 문자 토큰 빈도와 키워드별 문서 ID 저장
- 비교기간 관측 문서 수의 증감 계산; 비교 입력이 없으면 명시적 상태와 null 사용
- VERIFIED/SUPPORTED Fact의 canonical 문서 참조로 이슈별 통계를 재계산함
- 기존 AnalyticsSnapshot에 run version, 계산 기준 및 입력 SHA-256 저장
- IssuesToAnalyticsWorkflow를 연결하고 성공 시 `ANALYTICS_COMPLETED`로 전진함
- 외래키 검사가 켜진 DB에서 발견한 기존 duplicate cluster 부모/자식 저장 순서 오류 수정
- Alembic으로 생성한 DB에서 Evidence→Issue→Analytics, 재조회, rollback·재시도 검증
- unit/contract/integration 및 기존 1.0 전체 회귀 테스트: `234 passed` (기존 203개 + 31개)

실행 및 집계 기준은 `docs/aiporg2/analytics.md`에 기록했다. 감성은 기존 라벨
집계이고 키워드는 결정론적 문자 토큰 빈도다. 수집 완전성이나 형태소 기반
키워드 품질을 보장하지 않는다. Document/Evidence version lineage 보류는 유지한다.
다음 단계는 Phase 6 Grounded Narrative다.


## 2026-10-19 인계 문서에서 이관한 상세 작업 기록

아래 5~23차 기록은 당시의 결정·검증 이력이다. 뒤의 수정이 앞의 상태를 대체한다. 현재 상태와 다음 행동은 루트 `HANDOFF.md`를 우선한다.

## 이번 작업과 검증 (2026-10-16, 5차: 수집 정확도 + 파이프라인 연결)

사용자 요청: "구현 진행해. 최대한 정확도 올리는 수집 방향으로. 지금 있는
파이프라인도 한번 점검해도 좋고, 요구사항에 맞는 데이터 수집이 잘 되는지."
(4차에서 만든 Streamlit 콘솔을 실제 `streamlit run`으로 실행했을 때
`ModuleNotFoundError: No module named 'app'`가 나서 그것도 먼저 고쳤다 — 아래 참고.)

- **버그 수정(실행 실패):** 사용자가 실제로 `streamlit run streamlit_app/console.py`를
  실행했을 때 `app` 패키지를 못 찾는 에러가 났다. 원인: Streamlit은 스크립트의
  "자기 디렉터리"를 `sys.path`에 넣는데, `AppTest`(내 검증 방법)는 추가로 호출
  시점의 cwd도 `sys.path`에 넣어서 내가 저장소 루트에서 테스트할 때는 우연히
  통과했던 것 — 실제 `streamlit run`은 cwd를 넣지 않는다. `streamlit_app/console.py`
  맨 위에 `sys.path.insert(0, REPO_ROOT)`를 코드로 직접 추가해 cwd와 무관하게
  동작하도록 고쳤고, cwd를 `/tmp`로 바꾼 상태에서까지 재현·검증했다.
- **파이프라인 점검 결과(코드 재확인):** `app/collectors/naver_news.py`가
  `start=1, display=100` 고정 단일 요청만 하고 있어 바쁜 키워드의 월간 기사를
  최대 100건에서 잘라내고 있었다 — 가장 큰 정확도 문제로 보고 고쳤다(아래).
  `app/cleaning/service.py`(URL 정규화)와 `app/dedup/service.py`(URL/제목/본문
  3단계 exact match)는 검토 결과 설계대로 올바르게 동작, 변경 안 함.
- **수정 1 — naver 페이지네이션:** `start<=1000`까지 페이징하도록 변경(Naver API
  한도). 이전엔 한 키워드당 최대 100건만 가져왔다. unit test 2개 추가(여러
  페이지 순회, 1000건 상한에서 정지).
- **수정 2 — 신규 `MultiQueryCollectionToEvidenceWorkflow`:** 기존
  `CollectionToEvidenceWorkflow`는 project당 query 1개만 받고 workflow state를
  한 번만 전진시키는 구조라, 키워드 N개를 루프로 돌리면 state machine이
  두 번째 키워드부터 `InvalidStateTransitionError`를 던진다(각 상태는 한 번만
  전진 가능). 새 workflow(`app/workflows/multi_query_collection_to_evidence.py`)는
  N개 요청을 전부 수집한 뒤 상태를 한 번만 전진시키고, **수집된 raw document
  전체의 합집합**에 정제·중복제거·Evidence를 한 번에 적용한다 — 이게 "같은
  기사를 두 키워드에서 찾아도 한 건" 요구의 실제 구현이다. unit test 3개(빈
  요청 거부, 잘못된 상태 거부, 키워드 하나 실패해도 나머지는 진행) + 통합
  테스트 1개(두 키워드에 같은 URL이 섞여 있어도 canonical 문서 3건·Evidence
  3건으로 정확히 collapse되는 것을 실제 SQLite로 검증)로 확인.
- **수정 3 — repository 조회 메서드 추가:** `ProjectRepository.list()`,
  `CollectionRunRepository.list_by_project()`(둘 다 신규 schema 아님, 조회만).
  Streamlit "1. 월별 프로젝트"/"3. 수집 결과 검토"가 이제 세션이 아니라 DB에서
  직접 읽어, **앱을 재시작해도 프로젝트/수집 이력이 남는다**(4차의 "알려진
  한계" 중 하나를 해결).
- **Streamlit 콘솔을 새 workflow에 연결:** "2. 수집 설정·실행"이 이제
  `MultiQueryCollectionToEvidenceWorkflow`를 호출해 수집→정제→중복제거→Evidence를
  한 번에 실행한다. 이미 수집을 실행한 프로젝트는 폼을 숨기고 "새 프로젝트를
  만들어라" 안내만 보여준다(workflow state가 한 번만 전진하는 제약을 사용자에게
  투명하게 노출). "4. 통계·이슈 검토"는 더 이상 "미연결" 안내뿐이 아니라 실제
  canonical 문서 수·Evidence 수·문서 목록을 보여준다.
- **실제로 돌려서 검증:** 가짜(fixture) 네이버/다음 collector로 실제 Streamlit
  콘솔의 `_run_collection` 함수를 호출해 프로젝트 생성 → 키워드 2개×채널
  2개 수집 → DB 상태(`EVIDENCE_COMPLETED`, CollectionRun 4건, Document 4건,
  Evidence 2건 — 제목 중복 2건이 올바르게 걸러짐)까지 sqlite3로 직접 확인했고,
  `AppTest`로 "1→3→4" 화면이 그 데이터를 정확히 보여주는 것도 확인했다. 이
  과정에서 **또 다른 버그**를 발견·수정함: `_run_collection`을 고치면서
  `CREATED → QUERIES_READY` 전진 코드를 빠뜨렸는데, 새 workflow는 QUERIES_READY를
  요구해서 조용히 `InvalidStateTransitionError`로 실패하고 있었다 — 되돌려 고침.
- `tests_v2`+`tests` **260 passed**(254 + naver 2 + multi-query unit 3 + 통합 1).
  실 네이버/다음 API 네트워크 호출은 하지 않았다(키 미설정 상태로 검증).
- 기존 미커밋 변경은 보존했다. 수정 대상 파일은 전부 위 "사용자가 결정할 사항"
  과 무관한, 이미 M1로 예정돼 있던 작업이라 새 설계 결정 없이 진행했다.

## 이번 작업과 검증 (2026-10-16, 6차: .env 로딩 + 수집 기간 프리필)

사용자 보고: ".env에 키 넣었는데 Streamlit에서 못 가져오는듯" + "1단계에서
설정한 조사 기간을 2단계 수집 기간에 기본값으로 가져와야 하지 않나(수정은
허용)."

- **`.env` 미반영 원인 두 가지 확인:** (1) `app/core/config.py`가 `.env` 파일
  자체를 읽지 않음(이미 export된 쉘 환경변수만 읽음). (2) 사용자의 `.env`는
  1.0 스타일 이름(`NAVER_CLIENT_ID` 등, 접두사 없음)이고 Kakao 키가 아예 없음 —
  2.0은 `AIPORG2_` 접두사만 읽는 기존 설계라 설령 로드돼도 안 집히는 상태였음.
  (1)은 `streamlit_app/console.py`에 `python-dotenv` 로딩을 추가해 고쳤다
  (`requirements-dev.txt`에 `python-dotenv` 추가). (2)는 기존 네임스페이스
  분리 설계를 유지하고, 사용자가 `.env`에 `AIPORG2_NAVER_CLIENT_ID`/
  `AIPORG2_NAVER_CLIENT_SECRET`/`AIPORG2_KAKAO_REST_API_KEY`를 추가해야
  한다는 걸 위 "Streamlit 실행 방법"에 명시했다(대신 읽어주는 fallback은
  추가하지 않음 — 1.0/2.0 분리를 바꾸는 결정이라 임의로 하지 않았다).
  `get_settings()`가 `lru_cache`라 `.env` 수정 후 Streamlit 재시작이 필요하다는
  것도 함께 적었다.
- **`.env.example` 갱신(7차):** 기존 1.0 섹션은 그대로 두고 `AIPORG2_` 접두사
  섹션을 추가했다. 1.0 섹션에도 빠져 있던 `KAKAO_REST_API_KEY`를 추가함
  (`aiporg/collect/news.py`가 이 이름을 읽는데 템플릿에 없었던 기존 누락 —
  이번에 발견해 같이 고쳤다). `python-dotenv`로 실제 파싱 가능한지 확인함.
- **수집 기간 프리필:** `streamlit_app/console.py`의 "2. 수집 설정·실행"
  화면이 날짜 기본값을 `date.today()` 기준으로 독립적으로 잡고 있어 "1. 월별
  프로젝트"에서 설정한 조사 기간과 무관했다. 이제 프로젝트의
  `analysis_period.start`/`.end`를 기본값으로 넣고, 그 위에 "수정 가능하지만
  naver/daum collector는 아직 날짜로 결과를 거르지 않는다"는 caption을
  추가했다 — 날짜 입력이 실제로는 아직 수집 로직에 전달되지 않는다는 기존
  한계를 숨기지 않고 같이 알렸다.
- `AppTest`로 재검증: 프로젝트 생성(조사 기간 2026-10-01~10-16) → "2. 수집
  설정·실행" 진입 시 날짜 입력 기본값이 정확히 2026-10-01/10-16로 뜨는 것을
  확인. `.env` 로딩은 임시 파일로 별도 검증(`AIPORG2_*` 키가 올바르게
  `get_settings()`에 반영됨). 사용자의 실제 `.env`는 읽지도 수정하지도 않았다
  (내용 확인은 변수 이름만, 값은 보지 않음).
- `tests_v2`+`tests` 260 passed 유지(이번 변경은 UI 레이어 글루 코드라 기존
  테스트 범위 밖, 신규 테스트는 추가하지 않음).

## 이번 작업과 검증 (2026-10-16, 7차: 유튜브 collector)

사용자 요청: 유튜브 Data API v3와 Gemini 2.5 Pro를 "무료 한도 내에서" 쓰고
싶다, 파이프라인이 제대로 안 되어 있는지 확인해달라.

- **유튜브: 신규 구현.** `app/collectors/youtube.py`의 `YouTubeCollector`가
  `search.list`(키워드→영상 ID, 기본 1페이지/최대 50건)와
  `videos.list`(영상별 제목+설명+조회수/좋아요/댓글수, 1 unit/호출)를
  호출한다. 무료 일일 10,000 유닛 중 `search.list`가 100유닛으로 제일
  비싸서, 키워드 4~5개를 기본 설정으로 돌려도 수백 유닛 수준이라 여유
  있게 무료 한도 안에 든다(`max_pages`로 더 넓게 수집할 수도 있음,
  유닛 비용이 선형으로 늘어난다는 점은 호출 쪽에서 인지해야 함). 1.0의
  `aiporg/youtube/collector.py`를 참고했지만 그대로 재사용하지 않고 2.0
  `CollectorProtocol`(search/fetch 분리, repository 외 DB write 없음)에
  맞춰 새로 짰다 — 1.0은 project당 한 번에 여러 키워드를 묶어 `videos.list`
  를 50개씩 배치 호출하지만, 2.0은 키워드별로 `search()`를 따로 호출하는
  구조라 그 최적화는 그대로 옮기지 못했다(여전히 무료 한도 안에는 충분히
  든다). 댓글(`commentThreads.list`)은 구현하지 않았다 — 전 채널 공통으로
  아직 미구현인 "댓글 포함" 결정 사항(§확정된 결정)과 같이 처리할 대상.
  `AIPORG2_YOUTUBE_API_KEY`를 설정하면 Streamlit "2. 수집 설정·실행"에
  자동으로 뜬다. unit test 10개 추가(생성자 검증, 페이지네이션, fetch
  본문/통계 조합, malformed/서버 오류 처리).
- **채널 버그 발견·수정:** 유튜브를 끼워 넣으면서 보니
  `streamlit_app/console.py`가 모든 provider의 `SearchQuery.channels`를
  `ChannelType.NEWS`로 하드코딩하고 있었다(naver/daum만 있을 때는 우연히
  맞았음). `PROVIDER_CHANNELS` 매핑(naver/daum→NEWS, youtube→VIDEO)을
  추가해 고쳤고, 실제 수집 후 DB에 `channel='VIDEO'`로 저장되는 것까지
  확인했다.
- **Gemini: 구현하지 않음, 사용자 결정 필요.** LLM 서술 초안(M3)은 narrative
  출력/승인 계약(M0)이 아직 결정 전이라 임의로 설계하지 않았다(§사용자가
  결정할 사항 2번, 전부터 미해결로 남아 있던 항목). 모델 선택도 짚을 점이
  있다: `.env.example`의 기존 주석은 "Gemini 2.5 Pro"였지만, 무료 티어는
  flash 계열(`gemini-2.0-flash`/`gemini-2.5-flash`)이 Pro보다 훨씬 넉넉한
  무료 할당량을 준다 — "무료 한도 내에서" 쓰려면 Pro보다 flash가 현실적인
  기본값일 가능성이 높다. 진행하려면 (1) M0 narrative 출력 계약을 최소
  범위로 먼저 결정하고 (2) 모델을 확정해야 한다 — 다음 턴에서 사용자에게
  직접 물어봄.
- `tests_v2`+`tests` **270 passed**(260 + 유튜브 collector 10). 실제 YouTube
  API 네트워크 호출은 하지 않았다(키 미설정 상태로 검증, fixture collector로
  Streamlit 콘솔 전체 경로까지 확인).

## 이번 작업과 검증 (2026-10-16, 8차: Narrative 출력 계약 + Gemini 어댑터)

사용자가 7차 질문에 "최소 계약으로 narrative 저장 구조만 먼저 결정하고 구현"과
"모델은 gemini-2.0-flash"를 선택했다.

- **Narrative 출력 계약 결정·구현.** `docs/aiporg2/narrative-design.md`의
  2026-09-23 권장안(신규 테이블 없이 기존 `narratives.context` JSON에 구분
  가능한 envelope로 저장)을 그대로 채택해 구현했다. `app/schemas/narrative.py`에
  `NarrativeSentenceSchema`(text + fact_ids/evidence_ids/document_ids/
  analytics_paths 중 최소 1개 필수), `NarrativeGenerationSchema`(provider/
  model/prompt_version/input_snapshot_sha256/generated_at/usage),
  `NarrativeOutputSchema`(project_id/run/analytics_run_id/generation/
  sentences)를 **추가만** 했다 — 기존 `NarrativeContext`, `ReportSchema.context:
  NarrativeContext` 등 기존 계약은 이름·필드 그대로 유지. DB 컬럼/테이블도
  추가하지 않았다.
- **`NarrativeRepository`에 `save_output`/`get_latest_output` 추가.** 출력
  row는 `context` JSON에 `{"kind": "narrative_output", "data": {...}}`로
  저장하고, 입력 row는 기존 그대로(`kind` 키 없음 — `NarrativeContext`가
  `extra="forbid"`라 입력 row에는 구조적으로 그 키가 있을 수 없다는 점을
  이용한 구분, 신규 컬럼 없이 안전하게 구분됨). 기존 `get_latest()`는 `kind`
  있는 row를 건너뛰도록 한 줄만 고쳐서 **출력 row를 저장해도 기존 입력 조회
  결과가 그대로**임을 테스트로 확인했다.
- **버그 발견·수정(테스트 중):** `get_latest_output()`을 DB `created_at` 기준
  정렬로 처음 짰더니, SQLite `CURRENT_TIMESTAMP`가 1초 해상도라 같은 초 안에
  초안을 두 번 저장(재생성)하면 어느 게 "최신"인지 비결정적이었다. 대신 각
  출력이 자기 payload 안에 갖고 있는 `run.created_at`(Python 쪽에서 만드는
  고해상도 시각)으로 비교하도록 고쳤다 — 같은 초 안에 재생성해도 올바른
  최신 버전을 반환하는 것까지 테스트로 검증함.
- **`GeminiNarrativeAdapter` 신규 구현(`app/narrative/llm_adapter.py`).**
  `NarrativeContext` + `AnalyticsSnapshotSchema` + `Evidence` 목록을 받아
  프롬프트를 만들고, Gemini `generateContent`(`responseMimeType:
  application/json`)를 호출해 문장 배열을 받는다. **모델의 인용을 그대로
  믿지 않는다** — 각 문장의 `fact_ids`/`evidence_ids`/`document_ids`가 실제
  입력에 있는 id인지, `analytics_paths`가 실제 `analytics.metrics`의 키인지
  검사해서 근거 없는 문장은 조용히 버린다(전부 버려지면
  `NarrativeGenerationError(code="no_grounded_sentences")`로 실패). 키가
  없으면 이 어댑터를 생성할 수 없다(`ValueError`) — 호출하는 쪽이 기존
  `TemplateNarrativeService`로 fallback하는 책임을 진다(이 모듈 자체는
  fallback 로직을 갖고 있지 않음, 아직 그 상위 draft service를 만들지
  않았기 때문 — 아래 참고).
- **아직 안 한 것(의도적으로 범위를 좁힘):** (1) narrative draft orchestration
  service(Context+Analytics+Evidence를 모아 adapter 호출 후
  `save_output` 호출, 실패 시 template fallback) 없음. (2) Streamlit
  "5. 서술 편집" 화면 연결 없음 — 더 근본적인 이유가 있다: 이 콘솔에는 Issue
  확정과 AnalyticsSnapshot 생성이 **아예 연결돼 있지 않아서** `NarrativeContext`
  를 만들 입력 자체가 없다(Phase 4/5 코드는 `app/`에 있지만 `streamlit_app/
  console.py`가 호출 안 함). "5. 서술 편집" 미구현 안내 문구를 이 상태에
  맞게 고쳤다 — "LLM adapter가 없다"가 아니라 "adapter는 있는데 입력이
  없다"로. (3) 사용자 수정 UI, 버전 비교 UI 없음.
- `tests_v2`+`tests` **282 passed**(270 + narrative output schema 6 + Gemini
  adapter 9 + repository 1). 실제 Gemini API 네트워크 호출은 하지 않았다(가짜
  transport로 성공/부분 근거 탈락/전체 탈락/malformed/http 오류 각각 검증).

## 이번 작업과 검증 (2026-10-16, 9차: Issue/Analytics/Narrative를 콘솔에 연결)

사용자가 "다음할일 진행해도 돼"로 8차 끝에 적어둔 1순위(Issue/Analytics를
콘솔에 연결)를 진행 승인했다.

- **"4. 통계·이슈 검토" 확장:** 기존엔 canonical 문서·Evidence 수만 보여줬다.
  이제 workflow state에 따라 버튼이 뜬다 — `EVIDENCE_COMPLETED`에서 "이슈
  확정 실행"(`EvidenceToIssuesWorkflow`), `ISSUES_COMPLETED`에서 "통계 집계
  실행"(`IssuesToAnalyticsWorkflow`). 확정된 이슈 목록(fact/문서/출처/채널
  수, 세부 감성)과 AnalyticsSnapshot 전체 metrics(`st.json`)를 보여준다.
  공식 출처 목록 UI가 없어 전부 "비공식 출처"로 판정한다 — fact 검증은
  복수 독립 출처 조건으로만 통과한다. 공식 출처 정책은 결정 대상으로
  새로 추가함.
- **"5. 서술 편집" 신규 구현:** 이슈 선택 → 해당 이슈의 fact + 최신
  AnalyticsSnapshot + 전체 Evidence로 `NarrativeContext` 구성(`sentiment`는
  첫 subissue 것, 없으면 NEUTRAL; `keywords`는 이슈 label만 — 둘 다 현재
  파이프라인에 더 적절한 소스가 없어서 고른 임시값) → "초안 생성" 버튼.
  `AIPORG2_GEMINI_API_KEY`가 있으면 `GeminiNarrativeAdapter`, 없으면
  신규 `_template_sentences()` 헬퍼(새 템플릿을 만들지 않고 기존
  `TemplateNarrativeService.render_fact()`를 facts별로 직접 호출 — 그
  메서드의 "claim이 evidence 원문과 정확히 일치해야 한다"는 엄격한 검증을
  그대로 재사용). 결과는 `NarrativeRepository.save_output`으로 저장하고
  최신 버전을 문장별 근거 개수와 함께 바로 아래에 표시한다.
- **실제로 끝까지 실행해서 검증함:** 가짜 collector로 프로젝트 생성 → 키워드
  수집(채널 1개) → DB에서 `EVIDENCE_COMPLETED` 확인 → 이슈 확정 실행(이슈
  1건 확정) → 통계 집계 실행(`metrics`에 18개 키 생성 확인) → "5. 서술
  편집"에서 해당 이슈 선택 → 초안 생성 → 문장 "근거 문서에서 다음 내용이
  확인됨: 「...」"가 fact 1건 근거로 저장·표시되는 것까지 `AppTest`로 전부
  확인했다. 이게 이번 세션에서 만든 가장 긴 실제 수직 흐름이다(수집→
  Evidence→Issue→Analytics→Narrative 초안).
- 코드 변경은 전부 `streamlit_app/console.py`(새 `page_narrative`,
  `_template_sentences`, `_state_at_least`/`_WORKFLOW_STATE_ORDER` 헬퍼,
  `page_analytics` 확장)에 있다 — `app/` core 코드나 schema는 건드리지
  않았다(8차까지 만든 contract들을 그대로 소비하기만 함). 새 unit test는
  추가하지 않았다(UI 글루 코드, 이전 라운드들과 같은 이유) — 대신 위처럼
  `AppTest`로 전체 경로를 수동 검증했다. `tests_v2`+`tests` 282 passed 유지.

작업을 이어받는 도구는 완료 작업·변경 파일·검증 결과·막힌 점·다음 행동을 이 문서에 최신 상태로 갱신한다. 채팅 원문이나 비밀값은 기록하지 않는다.

## 이번 작업과 검증 (2026-10-16, 10차: 서술 수정·버전 비교, 승인은 의도적 미구현)

사용자가 "ㅇㅇ 다음 순번 진행"으로 9차 끝에 정리한 "정확한 다음 행동" 1번
(사용자 수정·버전 비교·승인 UI)을 승인했다.

- **신규 `NarrativeRepository.list_outputs(project_id)`**(조회 전용, 신규
  schema 아님) — 프로젝트의 모든 narrative 출력 버전을 반환한다.
  `get_latest_output()`과 같은 이유로 DB `created_at`이 아니라 각 버전의
  `run.created_at`으로 정렬한다(SQLite 1초 해상도 문제, 8차에서 이미 고친
  것과 동일 패턴). unit test 1개 추가(`list_outputs`가 최신순으로 두 버전을
  정확히 반환하는지).
- **"5. 서술 편집" 확장:** 버전 선택 드롭다운(버전명·시각·생성방식) → 선택한
  버전의 문장을 보여주고, 각 문장을 `st.text_area`로 수정할 수 있는 폼 추가.
  "수정 저장"을 누르면 **새 버전**(`output_version=f"edited-from:{이전
  버전}"`, `generation=None`, fact/evidence/document/analytics 참조는
  그대로 유지, 텍스트만 교체)으로 저장된다 — 이전 버전은 지워지지 않는다.
  빈 문장은 저장을 막는다.
- **버전 비교:** 버전이 2개 이상이면 두 개를 골라 나란히 보여주는 2열
  비교 화면을 추가했다(진짜 텍스트 diff는 아니고 단순 나란히 보기).
- **"최종 승인" 버튼을 의도적으로 비활성화 상태로만 추가했다.** 가짜로
  승인 상태를 저장하지 않는다 — narrative-design.md의 기존 설계(승인은
  narrative 버전+analytics_run_id+시각자료 버전+템플릿 버전을 함께 묶어서
  Report 계약 쪽에서 처리)를 따르려면 Visualization/Report 계약(M0)이 먼저
  결정돼야 한다는 설명을 캡션으로 달아뒀다. 이건 이번에 새로 발견한 제약이
  아니라 8차에서 이미 기록해둔 설계를 UI에 반영한 것뿐이다.
- **실제로 끝까지 실행해서 검증함:** 기존 fixture 프로젝트(9차에서 만든 것과
  같은 패턴)로 초안 생성 → 문장 수정 → 저장 → DB에서 두 버전(`template:v1`,
  `edited-from:template:v1`)이 각각 원본/수정 텍스트로 올바르게 저장된 것을
  직접 확인 → 버전 드롭다운이 최신순으로 뜨는 것, 버전 비교 화면이 두 버전의
  실제 텍스트를 양쪽에 정확히 보여주는 것, "최종 승인" 버튼이 비활성화
  상태로 렌더링되는 것까지 `AppTest`로 확인했다.
- 코드 변경은 `app/repositories/{narrative,sqlalchemy}.py`(조회 메서드
  추가)와 `streamlit_app/console.py`(`_render_narrative_sentences` 헬퍼,
  `page_narrative` 확장)에 있다. `tests_v2`+`tests` **282 passed**(신규
  테스트는 기존 narrative 테스트에 assertion 1줄 추가하는 형태라 전체
  개수는 그대로).

## 이번 작업과 검증 (2026-10-16, 11차: 구글 수집기)

사용자가 10차 끝에 정리한 "정확한 다음 행동" 1번(구글 수집기)을 "다음 진행해"로
승인했다. 같은 요청에서 "푸시해놨어"라고도 했지만 `git push`는 여전히
`Permission denied (publickey)`로 실패했다 — `ssh-add -l`로 확인해보니 **SSH
에이전트에 로드된 키가 아예 없다**("The agent has no identities."). 키 파일을
디스크에 추가한 것과 `ssh-agent`에 로드하는 것은 별개라, `ssh-add
~/.ssh/<키파일>`을 직접 실행해야 할 수 있다는 걸 사용자에게 알려야 한다
(아직 해결 안 됨, 커밋은 로컬에 계속 쌓이고 있음).

- **신규 `app/collectors/google_search.py`(`GoogleSearchCollector`):**
  공식 Google Custom Search JSON API를 쓴다(구글 결과 페이지 스크래핑이
  아님 — 약관 위반이라 피함). `search()`는 페이지당 1쿼리(무료 한도 하루
  100쿼리), `fetch()`는 naver_news.py와 같은 패턴으로 페이지를 받아 HTML을
  텍스트로 정제한다.
- **게시일 처리:** Google 검색 API는 임의 웹페이지의 게시일을 안정적으로
  주지 않는다. `pagemap.metatags`에서 `article:published_time` 등 흔한 키를
  찾아보고, 못 찾으면 **그 결과를 조용히 제외한다**(요구사항 §3.4 "게시
  시각을 확인할 수 없는 자료는 보류"를 그대로 적용 — 가짜 날짜를 넣지
  않음). unit test로 "날짜 있는 항목은 포함, 없는 항목은 빠짐"을 확인.
- **channel 분류 단순화(문서화된 제약):** 구글은 뉴스/블로그/커뮤니티를
  가리지 않고 찾아주는 "발견 경로"라 원문 채널을 안정적으로 구분할 수
  없다 — 전부 `ChannelType.NEWS`로 태깅하기로 하고 모듈 docstring과
  `streamlit_app/console.py`에 왜 그런지 적어뒀다. 더 정교한 URL 기반
  분류는 다음 행동 목록에 결정 대상으로 추가함.
- **Settings/`.env.example` 추가:** `AIPORG2_GOOGLE_API_KEY`,
  `AIPORG2_GOOGLE_SEARCH_ENGINE_ID`(cx) 둘 다 필요 — 1.0에는 구글 수집기가
  아예 없어서 대응되는 1.0 키가 없다는 것도 템플릿에 적었다.
- Streamlit 콘솔에 연결: `IMPLEMENTED_PROVIDERS`/`PROVIDER_LABELS`/
  `PROVIDER_CHANNELS`에 "google" 추가, `PLANNED_PROVIDERS`에서 구글 항목
  제거(커뮤니티만 남음). 가짜 collector로 `_run_collection`을 직접 호출해
  `channel='NEWS'`, `platform='google'`로 정확히 저장되는 것을 DB에서
  확인했고, `AppTest`로 8화면 전부(자격증명 있는 네이버/다음 포함 — 실제
  사용자 `.env`에 들어있는 진짜 키로 "구현됨" 상태가 뜨는 것도 확인됨)
  예외 없이 도는 것을 재확인했다.
- `tests_v2`+`tests` **292 passed**(282 + Google collector 10). 실제 Google
  API 네트워크 호출은 하지 않았다.

## 이번 작업과 검증 (2026-10-17, 12차: 댓글 수집)

사용자가 11차 끝에 정리한 "정확한 다음 행동" 2번(댓글 수집 컨벤션 구현)을
"댓글 수집 진행해줘"로 승인했다.

- **어느 채널에 구현했는가:** 유튜브만. naver/daum/google 세 곳 모두 댓글에
  접근할 수 있는 공식 API가 없다(naver 오픈 API는 뉴스 댓글 엔드포인트가
  없고, kakao 웹 검색도 마찬가지, 구글 커스텀 서치는 애초에 댓글 개념이 없는
  일반 웹 검색이다). 유튜브만 `commentThreads.list`/`comments.list`라는
  공식·문서화된 API가 있어서 거기에만 구현했다 — 다른 채널 댓글은 스크래핑
  없이는 못 하므로 범위에서 뺀 것이지 빠뜨린 게 아니다.
- **`YouTubeCollector` 확장(`app/collectors/youtube.py`):** `search()`가
  영상을 찾을 때마다 그 영상의 top-level 댓글도 `commentThreads.list`
  (1유닛/영상)로 가져와 **댓글 하나하나를 영상과 똑같은 `SearchResult`**로
  반환한다(URL에 `&lc={댓글ID}`를 붙여 구분, 상태 저장 없이 순수 URL
  파싱만으로 동작). `fetch()`는 URL에 `&lc=`가 있으면 `comments.list`
  (1유닛/댓글)로 그 댓글 하나만 다시 조회해서 `RawDocument`를 만든다 —
  기존 article fetch 경로와 완전히 같은 패턴이라 `CollectionService`/
  `MultiQueryCollectionToEvidenceWorkflow` 등 **다른 코드를 전혀 안
  건드렸다**(댓글이 그냥 검색 결과 하나 더 늘어난 것처럼 기존 파이프라인을
  그대로 통과함). 댓글이 비활성화된 영상은 `commentThreads.list` 호출이
  실패해도 그 영상 자체의 수집은 막지 않고 댓글만 건너뛴다(1.0
  `aiporg/youtube/collector.py`의 "로그만 남기고 계속" 패턴과 동일).
  `RawDocument.metadata`에 `document_type`("article"/"comment")과 댓글의
  경우 `parent_document_id`(영상의 document_id와 동일한 결정론적 공식으로
  계산 — 영상을 먼저 fetch해야 할 필요 없음)를 넣는다. 기본값
  `include_comments=True`, `max_comments_per_video=20`(생성자 인자로 조정
  가능, 비용은 영상당 최대 21유닛 — `search.list` 100유닛에 비하면 작음).
- **Analytics 분리(`app/workflows/issues_to_analytics.py`):** 댓글 컨벤션만
  추가하고 analytics가 모르는 척하면 "본문 언급량"에 댓글이 섞여버려서
  부정확해진다 — 그래서 `IssuesToAnalyticsWorkflow.run()`에서
  `document_type == "comment"`인 문서를 걸러내 `AnalyticsService.build()`
  에는 article만 넘기고, 댓글 수는 `comment_count`/`comment_document_ids`
  로 스냅샷 metrics에 따로 추가했다. **`AnalyticsService` 자체는 한 줄도
  안 고쳤다**(기존 254개+ 테스트가 보증하는 집계 로직을 그대로 두고, 필터링
  과 결과 병합만 호출부에서 했다). Streamlit "4. 통계·이슈 검토"는 이미
  `st.json(snapshot.metrics)`로 전체 metrics를 보여주고 있어서 추가 UI
  코드 없이 `comment_count`가 자동으로 뜬다 — 캡션 한 줄만 추가해 뭘
  의미하는지 설명했다.
- **의도적으로 결정하지 않고 남겨둔 것:** 댓글이 Evidence/Fact/Issue
  파이프라인에도 그대로 섞여 들어가는지는 **건드리지 않았다.** 기존
  `MultiQueryCollectionToEvidenceWorkflow`/`EvidenceToIssuesWorkflow`는
  `document_type`을 전혀 안 보고 모든 canonical 문서를 동일하게 취급하므로,
  댓글도 Evidence가 되고 (댓글 문구가 조건에 맞으면) Fact 후보가 될 수
  있다. "analytics 집계는 article/comment를 분리한다"는 기존 결정 문구에
  딱 그것만 적혀 있어서 그 범위만 구현했다 — 댓글을 애초에 Evidence/Fact
  대상에서 뺄지는 새로운 결정 사항으로 다음 행동 목록에 추가했다(임의로
  결정하지 않음).
- **실제로 끝까지 실행해서 검증함:** 가짜 유튜브 collector(영상 1개 +
  댓글 1개)로 Streamlit 콘솔의 `_run_collection` → 실제 Issue 확정 →
  Analytics 집계까지 돌려서, 댓글이 `unique_documents`에서는 빠지고
  `comment_count=1`로만 잡히는 것을 DB에서 직접 확인했다(처음엔 테스트
  fixture의 `published_at`을 프로젝트 조사 기간 밖으로 잘못 잡아서
  `unique_documents=0`이 나왔는데, 이건 내 테스트 스크립트의 실수였고
  고쳐서 재확인함 — 실제 구현 버그는 아니었다).
- unit test 신규: 유튜브 collector 3개(댓글 포함 검색, 댓글 비활성 영상
  건너뛰기, 댓글 fetch가 document_type/parent_document_id를 올바르게
  채우는지) + analytics workflow 2개(댓글 분리·댓글 없을 때 metrics
  그대로). 기존 유튜브 테스트 4개는 댓글 호출까지 포함하게 된 `search()`에
  맞춰 `include_comments=False`로 범위를 좁히거나 새 `document_type` 필드를
  기대값에 추가해서 고쳤다(동작이 바뀐 게 아니라 테스트가 몰랐던 새 동작을
  반영한 것). `tests_v2`+`tests` **297 passed**(292 + 5). 실제 YouTube API
  네트워크 호출은 하지 않았다.

## 이번 작업과 검증 (2026-10-17, 13차: 네이버 댓글 수집 + 다음 댓글 조사)

사용자가 "naver, daum은 댓글 어떻게 수집해? 그것도 파이프라인에 같이
스크랩하는거 있으면 좋겠는데"로 요청. 12차에서 "공식 API가 없는 채널은
스크래핑 없이는 못 한다"고 적었던 것을 실제로 확인·구현해본 결과.

- **네이버는 구현했다.** 네이버는 공식 Open API(검색 API)에는 댓글
  엔드포인트가 없지만, 실제 기사 페이지의 댓글 위젯 자체가 쓰는
  `https://apis.naver.com/commentBox/cbox/web_neo_list_jsonp.json`라는
  **비공식·미문서화 CBOX API**를 직접 `curl`/`requests`로 호출해보니
  **인증 없이, User-Agent 헤더만 있으면 동작**한다는 것을 확인했다(실제
  469개 댓글이 달린 기사로 라이브 검증). 그래서 `NaverNewsCollector`에
  유튜브와 같은 패턴으로 댓글 수집을 추가했다:
  `search()`가 기사의 naver 호스팅 링크(`n.news.naver.com/.../article/{oid}/{aid}`)
  에서 oid/aid를 뽑아 CBOX를 호출하고, 댓글마다 `cm={댓글번호}&pid={부모
  문서ID}`를 쿼리로 붙인 합성 URL의 `SearchResult`로 반환한다(`pid`는
  기사 URL — originallink든 naver link든 실제 선택된 것 — 로 미리 계산한
  `uuid5` 값이라 댓글 fetch 시점에 기사를 다시 조회할 필요가 없다).
  `fetch()`는 URL에 `cm`/`pid`가 있으면 CBOX를 다시 호출해 그 댓글만 찾아
  `metadata`에 `document_type="comment"`/`parent_document_id`/공감·비공감
  수를 채운다. 댓글이 꺼져있거나(`exposureConfig.status != COMMENT_ON`)
  댓글 API 호출 자체가 실패하면 **그 기사만 조용히 건너뛰고 기사 자체의
  수집은 막지 않는다**(12차 유튜브와 동일한 안전장치). 기본값
  `include_comments=True`, `max_comments_per_article=20`(1~100 범위
  검증).
- **라이브 검증 중 실제 버그 3개를 발견·수정했다**(전부 가정이 아니라
  실제 운영 API에 직접 호출해서 찾은 것):
  1. **댓글과 무관한 기존 버그**: `search()`가 `description`이 없으면
     결과 전체를 버리고 있었는데, 네이버가 실제로 빈 `description`을
     반환하는 기사가 존재함을 라이브로 확인(`koreadaily.com` 기사 1건).
     `description`은 애초에 저장도 안 되는 필드라 비어 있어도 버릴
     이유가 없어서, 존재 자체는 요구하지 않고 타입만 검증하도록 수정.
     이 버그는 같은 페이지에 그런 기사가 하나라도 섞이면 **최대 100건의
     결과 전체가 조용히 사라지는** 심각한 버그였다.
  2. **User-Agent 미설정 시 차단**: CBOX 엔드포인트는 User-Agent 없이
     호출하면 HTTP 200으로 위장한 Tomcat 403 Forbidden 페이지를
     반환한다 — 헤더 하나만 빠져도 "성공했지만 댓글 0개"로 조용히
     실패하는 상태였다. `User-Agent: Mozilla/5.0` 추가로 해결.
  3. **JSONP 파싱**: 실제 응답은 `_callback({...});`로 끝(세미콜론
     있음)인데, 처음 작성한 파싱 코드는 `_callback({...})`(세미콜론
     없음)를 가정해서 `JSONDecodeError: Extra data`로 실패했다.
     `.rstrip()` 후 세미콜론→닫는 괄호 순서로 벗겨내도록 수정하고,
     테스트 fixture(`_cbox_jsonp`)도 세미콜론 포함 형태로 고쳐서 앞으로도
     테스트가 현실과 다른 가정을 하지 않도록 했다.
- **엔드투엔드 라이브 검증**: 키워드 "행정공개"로 실제 `search()` 호출 →
  기사 1000건 + 댓글 1054건(합계 2054건) 수집 확인. 그 중 댓글 하나를
  실제로 `fetch()`해서 `metadata.parent_document_id`가 **같은 호출에서
  찾은 실제 기사 하나의 document_id와 정확히 일치**하는 것까지 직접
  확인했다(`parent article url: https://biz.sbs.co.kr/article_hub/...`).
- **Analytics/Workflow 쪽은 추가 수정이 필요 없었다.** 12차에서
  `IssuesToAnalyticsWorkflow`가 `document_type == "comment"`를 채널
  구분 없이 걸러내도록 만들어놔서, 네이버 댓글도 별도 코드 변경 없이
  자동으로 `comment_count`로 분리 집계된다(채널에 무관하게 동작하도록
  이미 설계되어 있었음을 재확인).
- **다음(Daum)은 조사만 하고 구현하지 않기로 결론 냈다 — 빠뜨린 게
  아니라 의도적 범위 제외다.** 실제 다음 기사 페이지(`v.daum.net`)를
  브라우저로 열어 네트워크를 직접 관찰한 결과, 댓글은
  `https://comment.daum.net/apis/v2/ui/post/{docId}/comments` 같은
  REST 엔드포인트에서 오긴 하지만, **모든 호출에 카카오의 "Alex" 댓글
  SDK(`comment.sdk.js`)가 자체적으로 발급하는 세션 단위 `Authorization`
  베어러 토큰이 필요**하다(`alex-version`/`alex-referer` 헤더도 함께
  요구). 네이버 CBOX처럼 User-Agent/Referer 헤더만으로 열리는 게
  아니라, SDK가 별도 핸드셰이크로 토큰을 발급받는 구조라 단순
  `requests` 호출로는 401만 반환된다. 이 토큰을 브라우저에서 가로채서
  서버 쪽 collector에 재사용하는 방법도 시도했으나, 실제 토큰 값은
  민감한 인증 정보라 추출하지 않았다(의도적으로 중단). 다음 댓글을
  수집하려면 기사마다 카카오 SDK가 로드된 실제 브라우저를 구동해야 하는데,
  이는 지금의 `requests` 기반 `CollectorProtocol` 패턴과 아키텍처가
  근본적으로 다르다(훨씬 무겁고 느림) — 그래서 새로운 결정 사항으로
  남겨두고 구현하지 않았다. 필요하면 별도 논의 후 헤드리스 브라우저
  기반 collector를 새로 설계해야 한다.
- unit test 신규: 네이버 collector 6개(빈 description 허용, 댓글 포함
  검색, naver 링크 없을 때 댓글 스킵, 댓글 꺼진 기사 스킵, 댓글 API 실패
  시 기사만 유지, 댓글 fetch의 document_type/parent_document_id 검증,
  댓글 재조회 실패 시 에러). `tests_v2`+`tests` **304 passed**(297 + 7).
  실제 네이버 API 네트워크 호출은 라이브 검증 때만 수동으로 했고, unit
  test 자체는 네트워크를 타지 않는다.
- **다음 정확한 다음 행동**: (1) 다음 댓글을 헤드리스 브라우저 기반으로
  구현할지, 아니면 포기하고 네이버/유튜브만으로 남길지 결정, (2) 댓글이
  Evidence/Fact/Issue 파이프라인에도 섞여 들어가는 문제(12차에서 적어둔
  미해결 사항)를 네이버 댓글까지 포함해서 처리할지 결정.

## 이번 작업과 검증 (2026-10-17, 14차: 커뮤니티 수집기 포팅 + 수집 현황 노출)

사용자가 "커뮤니티 관련 파이프라인은 아직 구현 전이었나? 기존에 있던
것같은데" 질문에 "1.0(`aiporg/collect/community/`)에는 robots.txt 준수·
rate limit·5개 사이트 파서까지 갖춘 완성도 있는 구현이 있지만 2.0
(`app/collectors/`)에는 아직 없다"고 답한 뒤, "포팅 진행하고, 추가적으로
더 필요한 로직있으면 수정. 그리고 2단계 수집 실행 이후에 키워드 자체는
보여줘 ... 수집한 기간, 키워드는 노출되도록"으로 두 가지를 요청했다.

### 1) 커뮤니티 수집기 포팅 (`app/collectors/community/`, 신규 패키지)

- **아키텍처:** 1.0의 `adapter.py`(오케스트레이션) + `discovery.py`(Naver
  웹검색으로 URL 발견 — 5개 사이트 모두 공식 커뮤니티 API가 없음) +
  `fetch.py`(robots+rate-limit 게이트) + `policy.py` + `ratelimit.py` +
  `robots.py` + `sites/*.py`(사이트별 파서)를 2.0 `BaseCollector`
  (`search()`/`fetch()`) 계약에 맞게 포팅했다. `policy.py`는
  **`config/community.yaml`을 1.0과 그대로 공유**한다(복제하지 않음) —
  이 파일의 모든 사이트는 기존과 똑같이 기본 `enabled: false`이고, 1.0부터
  있던 "운영자가 robots.txt·이용약관을 직접 검토한 뒤에만 활성화" 안전장치를
  그대로 유지했다(이 작업으로 어떤 사이트도 활성화하지 않았다).
  `store_author`/`store_comments_text` 토글은 포팅하지 않았다 — 2.0
  파서들은 애초에 작성자 닉네임·댓글 본문을 추출하는 코드 자체가 없어서
  (1.0도 어느 사이트든 실제로 추출한 적 없음) 끌 수 있는 기능이 아니라
  구조적으로 불가능하게 만들었다.
- **search()/fetch() 분리에 맞춘 구조 변경(버그 아님, 설계 차이):** 1.0의
  adapter는 발견→fetch→파싱을 한 번에 했지만, 2.0의 `SearchResult.
  published_at`은 필수 필드라 `search()` 시점에 실제 게시일을 알아야
  한다(아래 참고). 그래서 `search()`가 발견과 동시에 robots/rate-limit
  게이트를 통과한 후보의 HTML을 즉시 fetch+파싱해서 날짜를 얻고, 파싱
  결과를 메모리에 URL 기준으로 캐싱해둔다. `fetch()`는 이 캐시를 그대로
  반환해 **두 번째 HTTP 요청을 하지 않는다**(`CollectionService.collect()`가
  같은 collector 인스턴스에서 `search()` 한 번, 그 결과 각각에 `fetch()`를
  순차 호출하는 구조이기 때문에 가능함, `app/collection/service.py` 확인).
  캐시 미스(이론상 발생하면 안 되지만 방어적으로) 시에는 robots/rate-limit
  게이트를 다시 통과시켜 재fetch한다 — 게이트를 우회하는 경로를 만들지
  않았다.
- **실제로 라이브 검증하며 찾아 고친 문제들** (이번에도 "셀렉터를 읽기만
  하지 말고 실제 페이지에 돌려서 뭐가 나오는지 본다"는 이 세션의 방법론을
  그대로 적용함 — clien/fmkorea/theqoo/dcinside/ruliweb 실제 게시글을
  직접 가져와 1.0 파서를 그대로 돌려보고 출력을 확인):
  1. **1.0 파서는 게시일을 추출한 적이 없다.** `PostContent.posted_at`
     필드는 있었지만 어떤 사이트 파서도 채운 적이 없었다(1.0 자체
     SQLite에도 늘 NULL로 쌓였을 것). 2.0은 `published_at`이 필수라서
     이 포팅에서 5개 사이트 전부에 실제 셀렉터 기반 날짜 추출을
     추가했다(clien `.post_author .date`, fmkorea `.top_area .date`,
     theqoo `.side.fr`, dcinside `.gall_date[title]` 속성, ruliweb
     `.regdate`). 날짜를 못 찾으면 그 글은 버린다 — 구글 수집기(11차)의
     "게시 시각을 확인할 수 없는 자료는 보류" 결정과 동일한 정책이다.
  2. **fmkorea 제목 셀렉터가 실제로는 UI 배지를 잡고 있었다.** 실제
     게시글(`fmkorea.com/1567976329`)에 1.0 파서를 그대로 돌려보니
     제목이 "국축의 정석 - 대전 시티즌"이 아니라 "포텐"(인기글 배지
     텍스트)으로 나왔다. `og:title` 메타 태그(배지 없이 깨끗한 제목)를
     우선 쓰고 기존 셀렉터는 fallback으로 남겼다.
  3. **theqoo 제목 셀렉터가 전부 빗나가서 빈 문자열이 나오고 있었다.**
     실제 게시글에 `.title span`/`h1.title`/`.read_top .title` 중
     아무것도 안 맞고(`.title`만 써야 함 — 변경), 엉뚱하게 관련글
     목록의 열 머리글 "제목"이 title로 잡히는 걸 확인했다.
  4. **theqoo "조회수" 셀렉터가 실제로는 날짜를 읽고 있었다.** `.side.fr`
     노드의 텍스트("2026.06.14 19:19")를 숫자 추출 정규식에 넣어
     "조회수 2026"(연도)이라는 가짜 값을 만들고 있었다. 같은 노드를
     날짜로 올바르게 재사용하고, 실제 조회수는 이 페이지의 정적
     HTML에는 아예 없음을 확인해(스크립트 렌더링 추정) 0으로 둔 채
     추측하지 않았다.
  5. **발견된 URL 중 상당수가 게시글이 아니라 게시판/갤러리 목록
     페이지였다.** 1.0은 도메인만 걸러서 이런 목록 페이지도 그대로
     fetch를 시도했다(파싱만 실패). 사이트별 "이게 실제 게시글
     URL인지" 정규식(`POST_URL_PATTERNS`, 예: ruliweb `/read/\d+`)을
     추가해 fetch 전에 걸러서 rate-limit 예산을 낭비하지 않게 했다.
  6. **dcinside "미니 갤러리"(`/mini/board/view/`) 템플릿은 기존
     셀렉터로 파싱이 안 된다**(정식 갤러리와 DOM 구조가 다름, 라이브로
     확인). `GenericParser` 폴백도 이 템플릿에서는 본문을 못 찾아서
     결과적으로 조용히 버려진다(틀린 내용으로 수집되는 게 아니라 그냥
     빠짐) — 세 번째 dcinside 템플릿 전용 파서는 이번 범위에서는 만들지
     않고 알려진 한계로 남겼다.
- **엔드투엔드 라이브 검증 (전 사이트 강제 활성화한 임시 테스트, `config/
  community.yaml`은 건드리지 않음):** 키워드 "대전"으로 `search()` 실행 →
  clien 25건(사이트별 상한), theqoo 19건, ruliweb 10건, 총 54건의 실제
  게시글을 제목·본문·날짜까지 정확히 파싱해서 수집 확인. `fetch()`가
  `search()`의 캐시를 재사용해 추가 HTTP 요청 없이 동작하는 것도 호출
  수로 직접 확인했다.
  - **dcinside 0건**: 이 키워드에서는 Naver 웹검색이 "대전" 관련
    dcinside 갤러리 목록 페이지만 찾고 개별 게시글 URL을 못 찾아서다
    (`POST_URL_PATTERNS`가 그 목록 페이지들을 정확히 걸러냄). 다른
    키워드에서는 결과가 나올 수 있다 — 버그 아님.
  - **fmkorea 0건 — 이건 키워드 문제가 아니라 구조적이다.**
    fmkorea.com의 실제 robots.txt를 라이브로 읽어보니 이름이 등록 안 된
    일반 봇(`User-agent: *`)에게는 `/`, `/best`, `/best2`, `/humor`만
    허용하고 나머지 전부(`Disallow: /`) — 개별 게시글 경로는 전혀
    허용하지 않는다. 72건의 게시글 모양 URL을 찾았지만 전부 robots
    게이트에서 올바르게 차단됐다. 즉 fmkorea는 **robots.txt를 지키는
    이 설계로는 `config/community.yaml`에서 켜더라도 실질적으로 수집이
    안 된다** — 활성화를 고려하기 전에 사용자가 알아야 할 사실이라 위
    "사용자가 결정할 사항"에 추가했다.
- Streamlit 콘솔 연결: `IMPLEMENTED_PROVIDERS`/`PROVIDER_LABELS`/
  `PROVIDER_CHANNELS`에 "community" 추가(`ChannelType.COMMUNITY`),
  `PLANNED_PROVIDERS`(이제 빈 목록이라 완전히 제거)였던 커뮤니티 항목을
  정식 체크박스로 승격했다. `build_collectors()`는 네이버 키가 있으면
  `CommunityCollector`를 만든다(발견에 네이버 웹검색 API를 재사용하므로
  별도 키 불필요). 체크박스 자체는 "✅ 구현됨"으로 뜨지만, 활성 사이트가
  0개일 때는 그 아래에 "활성 사이트 없음 — 체크해도 0건, 오류 아님"이라는
  캡션을 따로 달아 왜 그런지 설명한다(키 없음과 사이트 비활성은 다른
  상태라 기존 "자격증명 없음" 문구 하나로는 설명이 안 됨).
- unit test 신규 30개: collector 11개(발견→게이트→파싱 흐름, 도메인 밖
  URL 스킵, 제외 패턴, robots 차단, rate-limit 상한, 날짜 없는 글 drop,
  fetch 캐시 재사용, 캐시 미스 시 게이트 재적용, 비활성 사이트 fetch
  에러, 생성자 검증) + parser 9개(5개 사이트 실제 라이브 구조를 반영한
  fixture로 제목/본문/날짜 검증, dcinside 미니갤러리 drop, generic
  fallback의 메타태그 날짜 추출과 drop) + policy 4개(공유 config 로드,
  도메인 매칭, 제외 패턴, 기본값 적용) + robots/ratelimit 6개. `tests_v2`+
  `tests` **334 passed**(304 + 30). unit test 자체는 네트워크를 타지
  않고, 위 라이브 검증은 별도로 수동 실행했다.

### 2) "2. 수집 설정·실행" — 이미 수집한 프로젝트에 키워드·기간 노출

- 기존에는 workflow state가 `QUERIES_READY`를 넘어간 프로젝트(이미 수집
  실행함)에 재진입하면 "이미 수집했다, 새 프로젝트를 만들어라" 경고만
  뜨고 끝이었다 — 이번에 수집한 키워드가 뭐였는지, 어느 기간으로
  설정했는지 다시 볼 방법이 없었다.
- `SqlAlchemyQuerySetRepository.get(project_id)`(기존에 있던 조회
  메서드, 신규 아님)로 저장된 키워드 목록을 가져와 경고 아래에
  `- 키워드` 목록으로 보여주고, `project.analysis_period.start/end`로
  조사 기간을 함께 보여주도록 `page_collect()`를 수정했다. 조사 기간은
  "1. 월별 프로젝트"에서 설정한 값이라는 것과, naver/daum 등 collector가
  아직 날짜로 결과를 거르지 않으므로(6차 기록) 실제 수집 문서가 이 기간
  안에만 있다는 보장은 아니라는 캡션을 같이 달아 과장하지 않았다.
- 가짜 collector로 프로젝트 생성 → 키워드 2개 수집 실행 → 같은 화면에
  재진입해 `AppTest`로 "조사 기간: 2026-10-01 ~ 2026-10-16"과 "수집한
  키워드 (2개): 키워드1, 키워드2"가 정확히 렌더링되는 것을 직접
  확인했다. 코드 변경은 UI 글루 코드뿐이라 신규 unit test는 추가하지
  않았다(이전 라운드들과 같은 이유).

## 이번 작업과 검증 (2026-10-17, 15차: robots.txt 버그 수정 + fmkorea 범위 제한 + 5개 사이트 전부 활성화)

사용자가 14차 보고 후 세 가지를 요청: (1) 네이버 대신 구글 웹검색을 쓰는 게
낫지 않냐는 질문(강제 아님), (2) "5개 사이트 모두 사용할거야", (3) "fmkorea는
/, /best, /best2, /humor이거 허용하는 범위에서는 크롤링해줘".

### 1) Naver vs Google 웹검색 — Naver 유지 권장, 변경 안 함

- Google Custom Search JSON API는 무료 한도가 **하루 100쿼리**뿐이고, 이미
  `GoogleSearchCollector`(11차)가 뉴스/일반 검색에 같은 할당량을 쓰고
  있다. 커뮤니티 발견만으로도 키워드 4개 × 5개 사이트 × 힌트 2개 = 40쿼리라
  Google 전체 할당량의 거의 절반을 커뮤니티 발견 하나에 써버린다.
- Naver 웹문서 검색 API(`webkr.json`)는 뉴스 검색 API와 별도 할당량이고
  한도가 훨씬 넉넉하다(이미 네이버 뉴스/댓글에 쓰는 것과 같은 키를
  재사용). 이번 세션에서 실제로 54건의 진짜 게시글을 정확히 찾아내는 것도
  라이브로 검증됨(14차).
- 결론: 바꿀 이유보다 안 바꿀 이유(할당량 충돌)가 커서 Naver를 유지했다.
  사용자도 "상관없으면 말고"라고 해서 강제 요청은 아니었음.

### 2) robots.txt 판정 라이브러리 교체 — 표준 라이브러리의 실제 버그 발견·수정

fmkorea 범위 제한을 구현하려고 `fmkorea.com/robots.txt`를 라이브로
`RobotsGate`에 그대로 돌려봤는데, `/`, `/best`, `/best2`, `/humor`처럼
robots.txt가 명시적으로 허용한 경로까지 전부 `False`(차단)로 나왔다.

- **원인(라이브로 재현·확인):** 표준 라이브러리 `urllib.robotparser`는
  RFC 9309가 요구하는 "가장 길게 일치하는 규칙이 이긴다"가 아니라 **파일에
  적힌 순서대로 첫 번째로 매칭되는 규칙을 적용**한다. fmkorea의
  robots.txt는 `User-agent: *` 블록 안에 `Disallow: /`를 먼저 쓰고 그 뒤에
  더 구체적인 `Allow: /best`/`Allow: /humor`를 쓰는, 실제 운영 사이트에서
  흔한 순서다 — 이 순서에서 `urllib.robotparser`는 앞의 `Disallow: /`만
  보고 뒤의 `Allow`는 아예 확인하지 않아, **robots.txt가 명시적으로 허용한
  경로까지 전부 차단 판정**하는 버그가 있다. 최소 재현 케이스로 직접 확인:
  `User-agent: *\nDisallow: /\nAllow: /humor`를 주면 `/humor`도
  `can_fetch()`가 `False`를 반환한다.
- **수정:** `app/collectors/community/robots.py`가 `urllib.robotparser`
  대신 `protego`(Scrapy가 쓰는 RFC 9309 준수 라이브러리, `requirements.txt`
  에 `protego==0.7.0` 추가)를 쓰도록 교체했다. 같은 fmkorea robots.txt로
  재검증하니 `/`, `/best`, `/best2`, `/humor`는 `True`, 개별 게시글의 맨
  URL(`/1234567890`)은 여전히 올바르게 `False`로 나왔다. 기존 4개 사이트
  (clien/dcinside/theqoo/ruliweb)의 실제 robots.txt로도 재검증해 동작이
  바뀌지 않음을 확인(회귀 없음 — dcinside의 "47"/"cat"/"dog" 등 명시적으로
  차단된 바쁜 갤러리는 여전히 `False`, 그 외 갤러리는 여전히 `True`).
  **이 버그는 fmkorea에만 해당하는 게 아니라 "Disallow: / 다음에 구체적인
  Allow"를 쓰는 어떤 사이트에도 영향을 주는 일반적인 문제였다** — 커뮤니티
  수집기 전체의 robots.txt 판정 정확성에 관한 버그 수정이지 fmkorea
  전용 임시방편이 아니다.
- unit test 신규 1개: `urllib.robotparser`였다면 실패했을 정확한 재현
  케이스(파일 순서상 먼저 나오는 `Disallow: /`, 뒤에 더 구체적인
  `Allow: /humor`/`Allow: /best`)를 회귀 테스트로 추가.

### 3) fmkorea를 robots.txt가 허용하는 범위(/, /best, /best2, /humor)로 제한

- **왜 "접두사만 붙이기"로는 안 되는가:** fmkorea 개별 게시글은
  `fmkorea.com/<번호>`(접두사 없음)와 `fmkorea.com/<게시판>/<번호>`
  둘 다로 같은 내용에 접근되는 걸 라이브로 확인했다(같은 `og:title`).
  그렇다고 Naver 검색으로 찾은 아무 게시글 ID에나 `/best/`를 붙여서
  robots.txt의 문자열 매칭만 통과시키는 건, 운영자가 robots.txt로 표현한
  **의도**(베스트/베스트2/유머 게시판의 글만 허용)를 기술적으로는 지키는
  척하면서 실제로는 어기는 것이다 — 이렇게 구현하지 않았다.
- **실제 구현(`app/collectors/community/collector.py`,
  `_resolve_fmkorea_url`/`_fmkorea_board_membership`):** 수집기 인스턴스당
  한 번, `/best`·`/best2`·`/humor` 게시판 목록 페이지 3개를 실제로
  가져와서 "그 페이지에 실제로 걸린 글 ID"만 신뢰할 수 있는 멤버십으로
  기록한다(`app/collectors/community/parsers.py`의
  `extract_fmkorea_board_post_ids` — best/best2는 게시판 접두사가 붙은
  링크로, humor는 접두사 없는 링크로 올라오는 걸 라이브로 확인해서 각각
  다르게 파싱). Naver 검색으로 찾은 fmkorea 후보는 (이미 접두사가 붙어
  있더라도 무시하고) 글 번호만 다시 뽑아서 이 멤버십 맵에 있는지 확인하고,
  있으면 검증된 게시판 접두사로 URL을 다시 만들어 그걸로만 robots
  검사·수집을 진행한다. 멤버십에 없는 글은 버린다 — 즉 **베스트/베스트2/
  유머에 실제로 걸린 글만, 키워드 관련성은 Naver 검색으로, 수집 허용
  범위는 robots.txt가 실제로 허용한 경로로 각각 독립적으로 검증**한다.
  목록 페이지 3개도 `_robots_gates`/rate limiter를 그대로 통과시키고(다른
  요청과 동일하게 예산을 쓴다), 한 번 만든 멤버십은 같은 인스턴스의 이후
  `search()` 호출(다른 키워드)에서도 재사용해 매번 다시 가져오지 않는다.
  `POST_URL_PATTERNS["fmkorea"]`도 기존 맨 URL 패턴에서
  `^/(?:best2?|humor)/\d+` 패턴으로 바꿨다(이제 위 재작성 단계를 거친
  뒤에만 이 패턴과 비교되므로).
- **라이브로 확인한 추가 사실, 구현에 반영:** fmkorea는 robots.txt와
  별개로 **자체 봇 차단 시스템("에펨코리아 보안 시스템")**이 있어, 이번
  작업 중 수동으로 테스트하다가(약 10초 간격 안에 여러 요청) 실제로
  IP가 차단당하는 것을 직접 겪었다(HTTP 430, "에펨코리아 보안 시스템"
  페이지 응답). 우회를 시도하지 않고 테스트를 즉시 중단했다 — 이 세션
  끝까지도 해당 IP가 fmkorea에 재접근 가능한지 재확인하지 못했다(아래
  "검증 못 한 부분" 참고). `config/community.yaml`의 fmkorea
  `min_interval_sec`을 기본값(3.0)보다 보수적인 6.0으로 올려 실제 운영
  중 같은 문제가 생길 가능성을 낮췄다 — 그래도 재발을 완전히 막는다는
  보장은 아니다.
- **검증 못 한 부분(투명하게 기록):** fmkorea의 게시판 목록 파싱
  (`extract_fmkorea_board_post_ids`)은 IP 차단 전에 실제로 가져온
  `/best`·`/best2` 페이지로 라이브 검증했지만, `/humor` 페이지는 셀렉터
  구조까지 라이브로 들여다보기 전에 차단당해서 **"bare numeric href가
  실제 게시글 링크 구조와 일치한다"는 가정은 차단 전 성공했던 한 번의
  관찰에만 근거**한다(unit test는 이 가정을 고정해서 검증하지만, 실제
  `/humor` 페이지에 그 가정과 다른 구조가 섞여 있을 가능성은 남아있다).
  `CommunityCollector(..., policies=load_policies())`로 실제
  `config/community.yaml`(fmkorea `enabled: true` 포함)을 써서 전체
  `search()`를 엔드투엔드로 돌리는 라이브 검증은 이번엔 못 했다 — 다음에
  fmkorea에 다시 접근 가능해지면 먼저 해야 할 일로 남긴다.
- `config/community.yaml`: 사용자 요청대로 **5개 사이트 전부
  `enabled: true`**로 바꿨다(각 사이트 robots.txt를 이번 세션에서 라이브로
  검토한 뒤의 운영자 결정, 날짜와 함께 주석으로 기록). 1.0과 공유하는
  파일이라 1.0 쪽 커뮤니티 어댑터를 쓰면 같은 설정이 그대로 적용된다 —
  의도된 동작이다.
- unit test 신규 8개: `extract_fmkorea_board_post_ids` 3개(best/best2
  접두사 링크, humor 비접두사 링크, best 게시판에서 비접두사 링크는 무시)
  + collector 4개(멤버십으로 올바른 접두사 해석, 멤버십에 없는 글 drop,
  Naver가 이미 접두사를 붙여 줬어도 다시 검증, 멤버십 캐시가 여러
  `search()` 호출에 걸쳐 재사용됨) + robots 회귀 1개(위 2번 참고).
  `tests_v2`+`tests` **343 passed**(334 + 9).

## 이번 작업과 검증 (2026-10-18, 16차: Visualization/Report 승인 계약 + VIS-02/07 편집·승인 UI)

사용자가 15차 끝에 정리한 "다음 행동" 중 "1. Visualization/Report 시각 자산
승인 계약 결정 → narrative '최종 승인' 버튼 연결"과 "2. 시각 자료 2종(채널
도넛, TOP10 카드) 편집 UI → HWPX 3쪽 시제품"을 "1,2까지 진행"으로 승인. 둘
다 끝까지 구현·검증했다(HWPX 포함, 아래 참고).

### M0 계약 결정: `docs/aiporg2/visualization-design.md` (신규 문서)

기존 `VisualizationAssetSchema`/`ReportSchema`는 `tests_v2/contracts/
test_fact_schema_contract.py`가 필드 집합·라운드트립을 그대로 고정해놔서
**한 글자도 바꾸지 않았다** — Narrative 출력 때와 같은 절차(완전히 새
모델만 추가)를 그대로 따랐다.

- **`VisualizationItemSchema`/`VisualizationOutputSchema`**(신규,
  `app/schemas/visualization.py`): `value`는 AnalyticsSnapshot 집계값을
  그대로 복사하며 UI에서 직접 못 바꾼다(AGENTS.md 7번) — `label`/
  `category`/`color`/`order`/`included`만 편집 가능. `slot_key`로 같은
  프로젝트의 여러 시각 자료(채널 도넛/TOP10 카드)를 구분한다(Narrative
  출력엔 없던 개념 — Narrative는 프로젝트당 흐름 하나뿐이라 슬롯이 필요
  없었음). `approved`/`approved_at`도 같은 패턴으로 `NarrativeOutputSchema`
  에 additive로 추가(기존 호출부는 전부 기본값 `False`/`None`으로 호환).
- **승인은 새 버전을 만들지 않고 같은 row를 제자리에서 갱신한다**
  (`approve_output`, narrative/visualization 둘 다). 내용이 아니라
  메타데이터만 바뀌는 작업이라 — 기존 `CollectionRunRepository.complete()`
  가 같은 PK row를 갱신하는 전례를 따름(append-only가 이 코드베이스의
  절대 규칙은 아니라는 걸 재확인).
- **"최종 승인"은 `Report`/`VisualizationAsset`에 필드를 추가하지 않고
  구현했다.** `Report` row가 존재한다는 사실 자체가 "그 순간 전부
  승인됐다"는 증거라서 승인 플래그를 따로 둘 이유가 없었다. 신규
  `app/report/approval.py::ReportApprovalService`가 narrative 최신 출력
  승인 여부 + `REQUIRED_VISUALIZATION_SLOTS = ("channel_donut",
  "top10_keywords")` 각각의 최신 출력 승인 여부를 확인하고, 하나라도
  없으면 `ReportApprovalError(missing=[...])`를 던져 Report를 만들지
  않는다. 전부 통과하면 승인된 시각 자료마다 기존
  `VisualizationAssetSchema` 식별자 row를 새로 등록하고 기존
  `NarrativeContext`(입력)와 묶어 기존 `ReportRepository.create()`로
  저장한다 — **새 schema도, 새 DB write 경로도 추가하지 않음.**
- **알려진 범위 제한(의도적으로 다음으로 미룸):** `ReportSchema.context`는
  여전히 입력 `NarrativeContext`이고 승인된 실제 문장
  (`NarrativeOutputSchema.sentences`)을 Report가 직접 담지 않는다 —
  narrative-design.md가 8차에 이미 지적한 간극, 이번 1차 최소 단위의
  필수 조건은 아니라고 보고 범위에서 뺐다. 승인된 문장은
  `NarrativeRepository.get_latest_output()`으로 계속 조회 가능.

### 신규 `app/visualization/service.py::VisualizationRenderService`

AnalyticsSnapshot.metrics에서 그대로 읽어온다(네트워크·LLM 호출 없음):
VIS-02 채널 도넛은 `metrics["channel_mentions"]`, VIS-07 TOP10 카드는
`metrics["keyword_frequencies"]`에서 상위 10개(건수 내림차순, 동률은
키워드 사전순). 각 항목의 `analytics_path`가 근거 경로가 된다. 결정론적 —
이미지 생성 모델 호출 없음(요구사항 §6.1 원칙).

### Streamlit 연결 (`streamlit_app/console.py`)

- **"5. 서술 편집"**: 비활성화해뒀던 "최종 승인" 버튼을 실제
  `approve_output`에 연결(최신 버전에서만 승인 가능, 승인 취소도 제공).
- **"6. 시각 자료 편집·승인"**(신규 화면): VIS-02/07 각각 탭으로 분리.
  생성/재생성, 버전 선택, 항목별 라벨/분류/색상/순서/표시 여부 수정(새
  버전으로 저장, 승인 상태는 미승인으로 리셋), 승인/승인취소(최신 버전만),
  2개 이상 버전일 때 나란히 비교.
- **"7. 보고서 미리보기"**(신규 화면): narrative + 시각 자료 2종의 승인
  상태를 표로 보여주고, 전부 승인된 경우에만 "최종 승인(보고서 생성)"
  버튼이 활성화되어 `ReportApprovalService`를 호출한다. 최근 승인본의
  report_id·생성 시각·포함 시각 자료 수를 보여준다.
- **실제로 찾은 버그(검증 중 발견·수정):** `page_report`의 최종 승인
  버튼 핸들러가 처음엔 `with session_scope(factory) as session:` 블록
  **안에서** `st.rerun()`을 호출하고 있었다. `st.rerun()`은 스크립트를
  즉시 중단시키려고 내부적으로 예외를 던지는데, 이 예외가 `with` 블록을
  빠져나가면서 `session_scope`의 `except Exception: session.rollback();
  raise`를 타버려서, **Report가 실제로 생성된 바로 그 트랜잭션이 커밋되기
  전에 롤백됐다** — 화면엔 에러도 안 뜨고(예외 자체는 정상적으로 처리됨)
  성공 메시지도 안 보이는데(rerun이 지워버림) DB에는 아무것도 안 남는,
  조용히 실패하는 버그였다. `AppTest`로 전체 흐름을 엔드투엔드 검증하다가
  "버튼 클릭은 성공하는데 `reports` 테이블이 비어 있다"로 발견했다.
  고치는 법은 다른 모든 버튼 핸들러가 이미 쓰던 패턴과 같다 —
  `st.success()`/`st.rerun()`을 `with session_scope(...)` 블록 **밖으로**
  빼서 커밋이 먼저 끝나게 한다.
- **실제로 끝까지 실행해서 검증함(`AppTest`):** 가짜 데이터로
  ANALYTICS_COMPLETED까지 세팅 → narrative 초안 승인 → VIS-02/07 둘 다
  생성·승인 → "7. 보고서 미리보기"에서 "최종 승인" 버튼이 활성화되고
  클릭 시 실제로 `Report`(시각 자료 2건 포함)가 DB에 저장되는 것까지
  sqlite3로 직접 확인했다.

### python-hwpx 연결 + HWPX 3쪽 시제품 (`app/report/hwpx_writer.py`)

- **python-hwpx 6.8.0을 연결했다.** `/Users/seoralee/Documents/Github/
  python-hwpx`(AIPORG와 별도 디렉터리, 사용자 결정 "별도 저장소"를 그대로
  따름)에 upstream(`airmang/python-hwpx`)을 **읽기 전용으로 local clone**만
  했다 — GitHub fork는 안 만들었다. 라이브러리 자체를 고칠 필요가 아직
  없어서(순정 API로 충분함) `requirements.txt`에 PyPI 고정 버전
  (`python-hwpx==6.8.0`)을 추가했다 — HANDOFF "HWPX 구현 방향"이 말하는
  "포맷 자체의 버그·부족 기능이 생기면 그때 fork로 전환" 조건이 아직 안
  와서, 지금은 fork보다 PyPI 고정이 더 단순하고 재현 가능한 선택이라고
  판단했다.
- **`build_cover_toc_summary(report, narrative_output, visualization_outputs,
  title=...)` → HWPX bytes.** 입력은 전부 이미 승인된 contract뿐이다
  (`ReportSchema`, 승인된 `NarrativeOutputSchema`, 두 슬롯의 승인된
  `VisualizationOutputSchema`) — 새 사실·숫자를 하나도 만들지 않는다
  (AGENTS.md 6번). 표지(제목·부제·승인 시각) → 목차(`hwpx.tools.toc_author.
  add_native_toc`+`mark_toc_dirty` — 페이지 재계산은 한컴이 다음에 열 때
  직접 함, 라이브러리의 쪽번호는 추정치일 뿐) → 요약(narrative 문장 +
  채널 도넛을 matplotlib PNG로 결정론적 렌더링해 삽입 + TOP10 키워드를
  편집 가능한 HWPX 표로 삽입) 순서. 표지/목차/요약 사이는
  `doc.styles.apply_paragraph_format(paragraphs=[...], page_break_before=
  True)`로 페이지를 나눈다. 두 슬롯 중 하나라도 없으면
  `HwpxPrototypeError`.
- **실제로 찾은 API 함정 2개(라이브 API 탐색 중 발견):** (1) `doc.
  set_paragraph_format(paragraphs=...)`는 6.0에서 deprecated된 legacy
  facade라 새 키워드(`paragraphs=`)를 받지 않는다 — `doc.styles.
  apply_paragraph_format(paragraphs=...)`(6.x 신규 표면)을 써야 한다.
  (2) `TextExtractor`/`validate_document`는 파일 경로나 `BytesIO`를
  받지만 **raw bytes를 직접 주면 `zipfile`이 터진다**(`'bytes' object
  has no attribute 'seek'`) — `BytesIO(raw)`로 감싸야 한다. 둘 다 unit
  test를 돌리다가 실제로 걸려서 고쳤다.
- **검증 방법과 한계(투명하게 기록):** 이 환경에 실제 한컴이 없어서
  "진짜로 열리는지"는 확인할 수 없다. 대신 python-hwpx 자체가 제공하는
  두 자동 검증을 썼다 — `hwpx.tools.validator.validate_document`(OWPML
  스키마 위반 검사)와 `hwpx.tools.package_validator.
  validate_editor_open_safety`(패키지 구조+재오픈+문서 검증을 묶은
  "에디터가 열기 전에 걸릴 만한 문제" 게이트, README가 "open-safety
  gate"라고 부르는 것) — 생성한 시제품이 둘 다 통과하는 것을 unit test로
  고정했다. **이것이 "실제 한컴에서 열림을 확인했다"는 뜻은 아니다** —
  라이브러리 저자가 측정한 "Hancom opens 476/476" 같은 수치의 근거가 되는
  바로 그 코퍼스 검증 도구이긴 하지만, 이 세션에서 우리 산출물로
  직접 돌린 건 구조 검증뿐이다. 실제 한컴 열림·페이지 배치·줄바꿈·표
  넘침 확인은 **여전히 사용자가 직접 해야 한다.**
- **Streamlit 연결 — "8. 출력·이력" 신규 구현(더 이상 "미구현" 패널
  아님):** 승인된 Report + narrative 출력 + 시각 자료 2종 출력이 전부
  있으면 시제품을 바로 만들어 `st.download_button`으로 내려준다. 하나라도
  없으면 "7. 보고서 미리보기에서 먼저 최종 승인하라"고 안내한다. 이제
  8화면 전체가 "미구현" 패널 없이 실제 코드로 동작한다 — 더는 쓰이지
  않는 `NOT_IMPLEMENTED_PAGES`/`page_not_implemented`도 같이 지웠다.
- **실제로 끝까지 실행해서 검증함(`AppTest`):** narrative 승인 → VIS-02/07
  생성·승인 → "7. 보고서 미리보기" 최종 승인 → "8. 출력·이력"에서 성공
  메시지와 다운로드 버튼이 실제 HWPX bytes와 함께 뜨는 것까지 전부
  확인했다. 이게 이번 세션에서 만든 가장 긴 수직 흐름이다(수집 이후
  단계만 보면 narrative 승인부터 HWPX 다운로드까지 끊김 없음).

### 테스트

신규 unit test 26개: `VisualizationOutputSchema`/`VisualizationItemSchema`
9개, `NarrativeOutputSchema.approved` 검증 2개(+기존 파일에 추가),
`VisualizationRenderService` 6개, 저장소 2개(narrative `approve_output`,
visualization output round-trip+승인), `ReportApprovalService` 3개(미승인
전체 차단, 전체 승인 시 Report 생성, 시각 자료 재편집 후 재승인 전까지
차단), `hwpx_writer` 3개(실제 내용 round-trip+구조 검증 통과, 필수 슬롯
누락 시 에러, 빈 항목일 때도 안 죽음). `tests_v2`+`tests` **369 passed**
(343 + 26). Streamlit 레이어는 이전 라운드들과 같은 이유로 신규 unit
test 없이 `AppTest`로만 수동 검증함(실행 스크립트는 세션 scratch에만
있었고 커밋하지 않음).

### 아직 안 한 것 / 다음 행동

- **실제 한컴에서 HWPX 시제품을 열어 확인하는 것** — 이 세션이 끝까지
  못 한 유일한 핵심 검증. "8. 출력·이력"에서 받은 파일을 사용자가 직접
  한컴으로 열어봐야 한다.
- VIS-01,03,04,06,08,09 및 일반 표는 이번 범위 밖(1차 최소 단위는
  VIS-02/07만) — HWPX 쪽도 같은 2종만 반영했다.
- `ReportSchema.context`에 승인된 narrative 문장을 실제로 번들링하는
  문제(위 "알려진 범위 제한" 참고) — M5/M6 HWPX 조립 작업 때 다시 결정.
- 전체 12쪽 HWPX 조립, DOCX/Markdown writer, python-hwpx fork(라이브러리
  자체 수정이 필요해지면) — M5/M6.

## 이번 작업과 검증 (2026-10-19, 17차: 2026-08 실데이터 1회 테스트 — 코드 변경 없음, 발견 사항만)

사용자가 8월/9월 키워드 목록을 주고 "일단 이걸로 해서 2026년 8월 테스트
한번 돌려줘. 시각자료는 이미지로 다운받아서 따로 데스크탑 안에 폴더에
넣어주고, llm으로 만든 생성형 문구들도 txt 파일로 일단 저장. streamlit말고
테스트로 진행"이라고 요청. **이번 라운드는 코드를 한 줄도 안 고쳤다** — 이미
있는 production 코드(collector/clean/dedup/evidence/fact/issue/analytics/
narrative/visualization/report-approval)를 Streamlit 없이 스크립트로
그대로 호출해서 실제로 돌려본 것뿐이고, 그 과정에서 중요한 데이터 품질
문제 3가지를 발견했다. 스크립트 자체는 세션 scratch에만 있었고 저장소에
커밋하지 않았다(1회성 실행 도구).

### 1차 시도 — 자격증명 없음 확인 후 가짜 데이터로 구조만 확인

이 환경에 `.env`가 아예 없고 `AIPORG2_*` 쉘 환경변수도 전혀 없어서, 먼저
사용자에게 물어봤고 "키 없이 템플릿/가짜 데이터로만 파이프라인 구조 확인"을
선택받아 가짜 collector(출처 2곳이 똑같은 문장을 보도하는 것처럼 꾸민 fixture)
로 전체 흐름(수집→정제→중복제거→Evidence→Fact→Issue→Analytics→템플릿
narrative→VIS-02/07→최종 승인)이 끝까지 연결되는 것만 확인했다. 이 결과물은
전부 `[TEST-가짜데이터]`로 표시해 실제 산출물과 섞이지 않게 했고, 사용자가
real 테스트를 요청하면서 바로 지웠다(세션 중 본인이 만든 scratch 산출물).

### 2차 — 사용자가 `.env`를 채워 넣은 뒤 실제 라이브 테스트

`.env`에 `AIPORG2_NAVER_CLIENT_ID/SECRET`, `AIPORG2_KAKAO_REST_API_KEY`,
`AIPORG2_YOUTUBE_API_KEY`, `AIPORG2_GOOGLE_API_KEY`,
`AIPORG2_GOOGLE_SEARCH_ENGINE_ID`(값은 비어 있었음 — 아래 참고),
`AIPORG2_GEMINI_API_KEY`가 채워졌다. 8월 키워드 4개
(AI 농기계·빠르미향 / '기후살인' / 이탈리아 순방·교황만나 '충남방문' 요청 /
석탄화력폐지지역 특별법·발전 공기업 통합본사 충남유치)로 프로젝트를 만들고
`streamlit_app/console.py`의 `build_collectors()`를 그대로 재사용해 naver·
daum·youtube·community 4개 채널(구글은 빠짐, 아래 참고) × 키워드 4개 = 16건
실제 네트워크 수집을 실행했다. 이후 EvidenceToIssuesWorkflow →
IssuesToAnalyticsWorkflow → Gemini narrative(이슈별 호출, 실패 시 템플릿
fallback) → VIS-02/07 생성·승인 → ReportApprovalService 최종 승인까지
**전부 production 코드 그대로, 끊김 없이 완주했다.**

결과물: `~/Desktop/AIPORG_2026-08/images/{01_channel_donut.png,
02_top10_keywords.png}`(차트 2개, 한글 폰트 포함 정상 렌더링 확인함),
`~/Desktop/AIPORG_2026-08/narrative_txt/*.txt`(이슈 6개, 문장 403개 —
아래 발견 2 때문에 이슈가 키워드 4개가 아니라 6개로 쪼개짐).

### 발견 1 (가장 중요, 우선 조치 필요): collector가 기사 본문이 아니라 페이지 전체 텍스트를 가져온다

실제 TOP10 키워드 결과가 "전체·있다·바로가기·기사보내기·댓글·닫기" 같은
**사이트 UI 문구**였고, Fact claim 문장도 상당수가 "｜동아일보 본문으로
바로가기 검색창 닫기 궁금하신 [...] 키워드를 검색해 보세요" 같은 **내비게이션/
관련기사 위젯 텍스트**였다(기사 본문이 아님). 원인을 코드에서 확인함:
`app/collectors/naver_news.py`의 `_TextExtractor`(`_clean_body`가 쓰는
HTMLParser 서브클래스)는 `<script>/<style>/<noscript>/<template>` 안의
텍스트만 건너뛰고, **`<nav>`/`<header>`/`<footer>`/메뉴/관련기사 영역은 전혀
걸러내지 않는다** — 사실상 페이지 전체의 보이는 텍스트를 그대로
`RawDocument.body`로 쓴다. `CleaningService`(`app/cleaning/service.py`)는
태그 제거·공백 정리만 하는 "순수 정규화" 계층이라고 스스로 문서화돼 있고
실제로도 본문 영역을 가려내는 책임을 지지 않는다 — 즉 **본문 추출(관련성
정제)은 collector의 책임인데 naver_news.py가 이를 구현하지 않은 것**이
근본 원인이다. `FactExtractionService._first_sentence()`는 이 오염된
body의 첫 "문장"(마침표 기준)을 그대로 claim으로 쓰므로, 메뉴 텍스트가
우연히 마침표로 끝나면 그게 Fact claim이 된다. **이 문제는 이번 테스트로
새로 드러난 것이지, 이전 세션들이 놓친 게 아니다** — 이전 세션들은
unit test의 손으로 쓴 깨끗한 fixture 본문으로만 검증했기 때문에
한 번도 실제 네이버 기사 페이지로 끝까지 돌려본 적이 없었다(coverage
자체는 전부 가짜 clean fixture). 영향 범위: naver 외 daum/youtube/
community collector도 각자 비슷한 패턴(전체 페이지 텍스트 vs 본문 영역)을
썼을 가능성이 있어 재확인이 필요하다 — 이번엔 naver만 코드로 직접 확인했다.
**우선순위 높은 다음 행동으로 기록**(아래 "다음 행동" 참고). 고치기 전까지는
실제 수집 데이터 기반 Fact/Issue/TOP10 키워드의 신뢰도가 낮다고 보는 게
안전하다.

### 발견 2: 이슈 그룹화가 키워드가 아니라 고정 3개 용어(기관/인물/지역) 기준이라는 설계 한계가 실데이터에서도 그대로 드러남

16차에서 가짜 데이터로 이미 적어뒀던 것과 같은 한계(`EvidenceToIssuesWorkflow`
→ `IssueDiscoveryService.discover()`가 `fact.entities`로만 묶고, 이
`entities`는 `[project.target.organization, primary_person, region]` =
["충청남도","도지사","충남"] 중 claim 문장에 등장하는 조합일 뿐 키워드와
무관함)가 실제 수집 데이터에서는 더 뚜렷하게 나타났다. 키워드 4개를 넣었는데
이슈는 6개가 나왔고, 그중 "충남"이라는 라벨 하나가 fact 337건(전체 403건
중 대부분)을 흡수했다 — "충남"이라는 글자가 들어간 문장은 전부 같은
이슈로 묶이기 때문에, 주제가 전혀 다른 기사들(AI 농기계든 석탄화력이든)도
"충남"만 포함하면 한 이슈로 합쳐진다. **매월 키워드 4~5개가 자동으로
4~5개 이슈로 나뉘는 것은 현재 구현으로는 보장되지 않는다** — 월간 보고서의
"이슈별 페이지" 구조를 실제로 만들려면 이슈 그룹화 로직 자체를 키워드
기준으로 바꾸거나 보완해야 한다(M2 대상, 아래 "다음 행동"에 기록).

### 발견 3: Gemini `gemini-2.0-flash` 호출이 전부 404로 실패, 템플릿 fallback은 설계대로 정상 동작

이슈 6건 전부 `GeminiNarrativeAdapter.generate()`가
`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent`
에서 HTTP 404를 반환했다(`app/narrative/llm_adapter.py`). 이 스크립트는
8차 결정대로 실패 시 해당 이슈만 템플릿으로 떨어지도록 짰고 실제로 6건
전부 정상적으로 템플릿 fallback → 문장 생성 → txt 저장까지 이어졌다 —
**fallback 설계 자체는 의도대로 동작을 확인함.** 404의 정확한 원인(모델명이
이 API 키/프로젝트에서 바뀌었는지, 아예 사용 불가 모델인지)은 조사하지
않았다 — 다음 행동으로 남긴다(`gemini-2.5-flash`/`gemini-flash-latest` 등
대안 모델명 확인, 또는 `GET /v1beta/models?key=...`로 실제 사용 가능한
모델 목록 조회부터 필요).

### 그 외 확인한 것

- **구글 수집기는 이번 라운드에서 빠졌다** — `.env`의
  `AIPORG2_GOOGLE_SEARCH_ENGINE_ID` 값이 **비어 있었다**(`AIPORG2_GOOGLE_API_KEY`는
  채워져 있음). `build_collectors()`는 둘 다 있어야 구글 collector를
  만들기 때문에 자동으로 빠졌다 — 오류가 아니라 설계대로의 동작. 구글도
  테스트하려면 Custom Search Engine ID(cx) 값을 `.env`에 추가해야 한다.
- **수집량 자체는 매우 컸다** — 키워드 4개 × 채널 4개 = 16건 수집에서
  고유 문서 4052건이 나왔지만, 2026-08 분석 기간으로 거른 뒤에는 373건만
  남았다(`'기후살인'` 키워드 하나가 뉴스에서만 2984건 발견 — 인용부호가
  포함된 키워드가 검색엔진에서 예상보다 훨씬 넓게 매칭된 것으로 보임).
  naver/daum collector가 아직 날짜로 결과를 거르지 않는다는 기존 기록
  (6차)과 정확히 일치하는 동작 — 새로 생긴 문제가 아니라 기존에 알려진
  한계가 실제 규모로 확인된 것.
- fmkorea를 포함한 커뮤니티 수집은 이번엔 봇 차단 없이 조용히 0건(해당
  없음)으로 끝났다 — 15차에서 겪었던 차단이 이번엔 재현되지 않았다(완전히
  해소됐다는 뜻은 아님, 단발성 테스트라 결론 내리기엔 이르다).

### 다음 행동 (우선순위 순)

1. ~~naver_news.py(및 다른 collector들) 본문 추출을 "페이지 전체 텍스트"에서
   "실제 기사 본문 영역"으로 좁힌다~~ — **해결됨(18차).**
2. ~~Gemini 404 원인 확인 — 모델명 확정 또는 사용 가능한 모델 목록 조회.~~ —
   **해결됨(19차): `gemini-2.5-flash`로 교체.**
3. ~~이슈 그룹화를 키워드 인지형으로 보완할지 결정(M2) — 발견 2.~~ —
   **해결됨(20차): 그룹화 키를 `fact.entities`에서 근거 문서의 query로
   교체.**

이번 라운드는 **의도적으로 코드를 고치지 않았다** — 사용자가 "테스트 한 번
돌려봐"라고 요청했을 뿐이라, 발견한 문제를 바로 고치는 대신 결과와 원인을
보고하고 우선순위만 기록했다.

## 이번 작업과 검증 (2026-10-19, 18차: collector 본문 추출 수정 — 발견 1 해결)

17차에서 찾은 "우선순위 1번"(collector가 기사 본문이 아니라 페이지 전체
텍스트를 가져온다)을 사용자가 "이 부분 수정하자"로 승인해 바로 고쳤다.

- **원인 재확인**: `naver_news.py`뿐 아니라 **`daum_news.py`·
  `google_search.py` 셋 다 똑같은 `_TextExtractor(HTMLParser)` 클래스를
  거의 그대로 복사해서 쓰고 있었다** — `<script>/<style>/<noscript>/
  <template>`만 건너뛰고 `<nav>`/`<header>`/`<footer>`/관련기사 위젯은
  전혀 거르지 않는, 셋이 공유하는 동일한 결함. 17차는 naver만 코드로
  확인했었는데, 이번에 나머지 둘도 같은 복사-붙여넣기 버그를 갖고 있다는
  걸 확인했다.
- **해결책**: 직접 셀렉터 블록리스트를 손으로 짜는 대신(사이트마다 구조가
  다 달라서 일반화가 어려움 — naver/daum/google은 community collector와
  달리 특정 몇 개 사이트가 아니라 임의의 외부 퍼블리셔 페이지를 가져오기
  때문에 사이트별 전용 셀렉터 방식 자체가 안 맞음), 뉴스 사이트 본문
  추출에 특화된 성숙한 라이브러리 `trafilatura`(PyPI, `requirements.txt`에
  `trafilatura==2.3.1` 고정)를 새로 연결했다. 신규
  `app/collectors/content_extraction.py::extract_article_text()`가
  trafilatura로 먼저 시도하고, trafilatura가 "기사 형태를 못 찾겠다"며
  `None`을 반환하는 경우(너무 작거나 비정형적인 페이지)에만 기존 whole-page
  추출(이름을 `_LegacyWholePageExtractor`로 바꿔서 그대로 보존)로
  대체한다 — 실패를 에러로 올리지 않고 조용히 성능이 낮은 경로로
  내려가게 함.
- `naver_news.py`/`daum_news.py`/`google_search.py` 셋 다 각자의
  `_TextExtractor` 클래스를 지우고 `_clean_body()`가 이 공용 함수를
  호출하도록 바꿨다 — 중복 제거 + 세 곳 동시 수정.
- **독자 댓글은 trafilatura에서 명시적으로 제외했다**(`include_comments=False`)
  — 댓글은 이미 별도 `RawDocument`(`document_type="comment"`)로 수집하는
  기존 컨벤션(12·13차)이 있어서, 기사 본문에 사이트 자체 댓글 위젯 텍스트가
  다시 섞여 들어가면 중복이 된다.
- **기존 unit test 3개(naver/daum/google 각 1개, "첫 문장 둘째 & 셋째"
  고정 fixture)를 바꾸지 않고 그대로 통과시켰다** — trafilatura가 이렇게
  작은 테스트 fixture에서는 보통 `None`을 반환해 레거시 경로로 떨어질
  것이라 예상했는데, 실제로 테스트해보니 trafilatura가 `\n` 구분자로
  텍스트를 반환했고(레거시 경로가 전혀 아님) 이후 공통 공백 정규화
  (`\s+` → 단일 스페이스)를 거치면서 우연히 기존 기대값과 정확히 일치했다
  — 바꾸기 전에 직접 실행해서 확인하고 진행했다(추측으로 넘어가지 않음).
- **라이브 검증**: 17차 때 문제가 됐던 실제 네이버 기사 URL
  (`n.news.naver.com/mnews/article/047/0002532680`)을 `NaverNewsCollector.
  _clean_body()`로 다시 통과시켜 "바로가기"/"닫기" 같은 메뉴 텍스트가
  사라지고 실제 기사 본문(서산 방문, 박수현 지사 발언 등)만 남는 것을
  직접 확인했다. 또한 nav/header/footer/관련기사위젯이 섞인 합성 HTML로
  trafilatura가 실제로 그 영역들을 걸러내는지, 레거시 fallback이 trafilatura
  실패 시(`trafilatura.extract`를 mock으로 `None` 강제) 제대로 동작하는지도
  unit test로 고정했다(`tests_v2/unit/test_content_extraction.py`, 4개).
- `tests_v2`+`tests` **373 passed**(369 + 4). 기존 collector 테스트는 한
  줄도 안 바꿨다.
- **이번 수정 범위 밖(다음 행동으로 남김)**: youtube collector는 API
  JSON 응답(제목+설명)만 쓰고 임의 HTML 페이지를 파싱하지 않아 이 문제와
  무관함(재확인 완료, 수정 불필요). community collector는 14차부터
  사이트별 전용 파서를 쓰고 있어 원래도 이 문제가 없었다(재확인 완료).
  17차의 발견 2(이슈 그룹화가 키워드가 아니라 고정 3용어 기준)와 발견
  3(Gemini 404)은 이번 라운드에서 건드리지 않았다 — 이번은 발견 1만
  범위로 한정해 진행했다.

## 이번 작업과 검증 (2026-10-19, 19차: Gemini 404 원인 확인 + 모델 교체 — 발견 3 해결)

17차 발견 3(모든 Gemini 호출이 404)을 조사했다. 실제 `.env`의 Gemini 키로
`GET https://generativelanguage.googleapis.com/v1beta/models`를 라이브로
호출해 확인한 결과 **`gemini-2.0-flash`가 이 API의 사용 가능한 모델 목록에
더 이상 없다**(8차에 결정했던 모델이 그 사이 폐기/교체됨 — Google 쪽
변경이라 이 저장소의 과거 결정이 틀렸던 게 아니라 외부 서비스가 바뀐
것). 같은 키로 `gemini-2.5-flash:generateContent`를 직접 호출해 200 OK와
정상 응답을 라이브로 확인한 뒤 기본 모델을 교체했다 — "무료 티어가
2.5-pro보다 넉넉함"이라는 8차의 원래 선택 기준(pro가 아니라 flash 계열)은
그대로 유지하고, 그 계열 안에서 지금 실제로 동작하는 버전으로만 바꿨다.
`gemini-flash-latest`(항상 최신 flash를 가리키는 별칭)도 목록에 있었지만,
코드 변경 없이 동작이 바뀔 수 있어(예측 불가능한 회귀 위험) 명시적 버전
고정(`gemini-2.5-flash`)을 택했다.

- 변경: `app/narrative/llm_adapter.py`(`GeminiNarrativeAdapter.__init__`의
  `model` 기본값), `.env.example`, `streamlit_app/console.py`의 안내 문구.
  `tests_v2/unit/test_gemini_narrative_adapter.py`의 기본값 검증 테스트
  1개를 새 모델명에 맞게 고쳤다(다른 테스트는 `model=`을 직접 지정하므로
  영향 없음).
- `tests_v2`+`tests` **373 passed** 유지(테스트 1개 수정, 개수 변화 없음).
- 다음 행동: 17차 발견 2(이슈 그룹화가 키워드가 아니라 고정 3용어 기준)만
  남았다.

## 이번 작업과 검증 (2026-10-19, 20차: 이슈 그룹화를 키워드 기준으로 교체 — 발견 2 해결)

17차 발견 2(`EvidenceToIssuesWorkflow`가 키워드가 아니라 기관/인물/지역
고정 3용어 기준으로 이슈를 묶어서, 8월 키워드 4개가 이슈 6개로 쪼개지고
"충남"이라는 라벨 하나가 fact 337건을 흡수했던 문제)를 사용자가 "ㅇㅇ
진행"으로 승인해 고쳤다.

- **설계 결정**: `IssueDiscoveryService.discover()`의 그룹화 키를
  `fact.entities`(claim 문장에 등장하는 고정 용어 조합)에서 **그 fact의
  근거 문서들이 어떤 키워드(query)로 수집됐는지**로 바꿨다. `CleanDocument.
  query`는 이미 존재하는 필드(신규 schema 아님) — 검색할 때 사용자가 실제
  타이핑한 키워드 그대로이므로, "고정 용어 매칭"보다 "근거 있는 라벨"
  원칙에 더 가깝다(추론이 아니라 사용자 입력 그대로). 한 fact의 근거
  문서들이 서로 다른 키워드에서 왔다면(같은 기사가 두 키워드에서 발견되는
  드문 경우) **가장 많이 나온 키워드**로 배정하고, 동률이면 사전순으로
  결정론적으로 고른다.
- **부수 효과(의도한 개선)**: 이전엔 claim 문장에 기관/인물/지역 고정
  용어가 하나도 없으면 그 fact가 **어느 이슈에도 안 들어가고 조용히
  버려졌다**. 키워드 기준으로 바꾸면서 모든 문서가 반드시 검색 키워드를
  갖고 있으므로 이 누락 경로 자체가 없어졌다 — 버그는 아니었지만 부정확한
  동작이었다.
- **변경 파일**: `app/issues/discovery.py`(시그니처에 `query_by_document`
  추가, 그룹화 로직 교체), `app/workflows/evidence_to_issues.py`(documents
  dict에서 `query_by_document` 구성해 전달 — 이미 있는 `source_by_document`/
  `channel_by_document`와 같은 패턴). **새 schema도 새 workflow 상태도
  추가하지 않았다** — 기존 `IssueCandidateSchema.label: str`에 다른 내용을
  넣을 뿐, 필드 자체는 그대로.
- **기존 테스트 재확인 결과**: `tests_v2/integration/test_evidence_to_
  issues_workflow.py`는 두 문서가 이미 같은 query를 공유하는 fixture라서
  **한 글자도 안 고쳤는데 그대로 통과**했다(우연이 아니라, 그 테스트가
  애초에 라벨 값 자체를 assert하지 않고 묶임 결과만 확인했기 때문). 반면
  `tests_v2/unit/test_issue_discovery.py`는 entity 기준 그룹화를 직접
  테스트하고 있어서 전면 재작성했다(4개: 쿼리 기준 그룹화, 한 fact의
  근거가 두 쿼리에 걸칠 때 다수결+결정론적 동률 처리, query_by_document
  누락 시 에러, entities 없어도 더 이상 누락되지 않음).
- `tests_v2`+`tests` **375 passed**(373 − 2개 교체 + 4개 신규 = 375).
- **이번 수정 범위 밖**: `fact.entities` 필드 자체와
  `FactExtractionService`가 그걸 채우는 로직은 그대로 뒀다(같은 claim+
  event_date+entities 조합을 "같은 사실"로 묶는 중복 판정에는 여전히
  쓰인다 — 이슈 그룹화와는 다른 관심사라 건드리지 않음). 17차에서 적어둔
  발견 1·2·3이 전부 해결됐다 — 다음 라운드는 새 요청을 기다린다.

## 2026-10-19 실데이터 재검증 (20차 수정 후) + 21차: TOP10 키워드 품사 필터 교체

사용자가 "그럼 8월 분석 다시 돌려도 돼?"로 승인해 18·19·20차 수정을 모두
반영한 2026-08 실데이터 테스트를 다시 돌렸다.

### 재검증 결과

- **이슈 그룹화 수정이 정확히 의도대로 동작함을 확인**: 키워드 4개 →
  이슈 정확히 4개(`AI 농기계, 빠르미향`/`'기후살인'`/`이탈리아 순방, 교황만나
  '충남방문' 요청`/`석탄화력폐지지역 특별법, 발전 공기업 통합본사 충남유치`),
  라벨이 키워드 그대로. `narrative_txt/` 파일명도 이제 이 4개 키워드
  그대로다.
- **collector 본문 추출 수정도 확인**: narrative 문장에 더 이상
  "바로가기"/"기사보내기"/"닫기" 같은 메뉴 텍스트가 안 보이고 실제 기사·댓글
  내용만 나온다.
- **Gemini는 이번엔 404가 아니라 429(rate limit)로 4건 전부 실패** — 모델명
  문제는 해결됐으나 무료 티어 분당/일일 호출 한도에 걸림(5번째 연속 호출
  근처). 템플릿 fallback이 설계대로 정상 작동해 문장 4039개가 전부 생성됨.
- **재실행 중 발견한 새 운영 이슈(코드 버그 아님)**: 같은 키워드로 새
  프로젝트를 다시 만들어 수집하면 `documents.id`가 URL 기반
  결정론적 해시(`uuid5(NAMESPACE_URL, url)`)라서 이전 테스트 프로젝트가
  이미 수집해둔 같은 URL과 전역 PK가 충돌해 `UNIQUE constraint failed`로
  수집 자체가 실패했다. `documents.id`가 project별로 scope되지 않고 테이블
  전체에서 유일해야 하는 게 원인 — 매달 다른 프로젝트를 쓰는 정상 운영
  패턴(이번 달 키워드와 지난 몇 달 키워드가 우연히 같은 URL을 다시 찾는
  경우)에서도 이론적으로 재현 가능한 설계상 한계다. 이번엔 이전 세션에서
  내가 만든 테스트용 프로젝트 2개(가짜 데이터 1개 + 수정 전 실데이터 테스트
  1개)를 직접 지워서 우회했다 — **코드는 고치지 않았다**, 다음 결정 목록에
  "documents.id 충돌 가능성(동일 URL을 다른 프로젝트가 재수집할 때)"으로
  남긴다.

### 21차: TOP10 키워드가 여전히 지저분한 문제(사용자: "top10 키워드 너무
말이 안됨") — 품사 기반 명사 필터로 교체

collector 수정(18차)으로 사이트 메뉴 텍스트는 사라졌지만, TOP10은 여전히
"있다·폭염·있는·ai·지난·한다·위해·충남·var·함께"처럼 한국어 조사/동사/부사와
본문에 섞여 들어온 자바스크립트 토큰("var")이 상위를 차지했다 — 원인은
`AnalyticsService`의 키워드 집계가 `docs/aiporg2/analytics.md`에 이미
문서화돼 있던 대로 "형태소 분석이 아니라 2글자 이상 문자 토큰 빈도"였기
때문(새로 생긴 버그가 아니라 기존에 알려진 한계가 실제로 드러난 것).

- **해결책**: 이미 `requirements.txt`에 있던(1.0 유튜브 키워드 추출에 쓰던)
  `kiwipiepy`를 `app/analytics/service.py`에 연결했다. `kiwi.tokenize()`로
  형태소 분석한 뒤 **일반/고유명사(NNG/NNP)만, 2글자 이상** 남긴다 — 조사·
  동사·부사·외국어(SL, "AI"/"var"/"fixed"/"false"가 전부 이 태그)·의존명사
  (NNB, "것"/"수"/"때문")는 전부 이 필터 하나로 자동 제외된다(별도 불용어
  사전을 만들 필요가 없었다 — 라이브로 `kiwi.tokenize()`에 실제 노이즈
  문장을 넣어 태그를 직접 확인하고 설계함). `kiwipiepy`를 쓸 수 없는
  환경에서는 기존 문자 토큰 빈도 방식으로 자동 대체하고,
  `metrics["basis"]["keywords"]`에 실제 어느 방식을 썼는지 기록한다.
- **기존 테스트 호환성**: `test_analytics_service.py`의 기존 키워드
  fixture(`title="정책", body="정책 지원 123"`)로 `kiwi.tokenize()`를
  직접 실행해 기존 기대값(`{"정책": 6, "지원": 3}`과 동일한 비율)이 그대로
  나오는 것을 라이브로 먼저 확인한 뒤 교체했다 — 추측으로 넘어가지 않음.
  기존 테스트 9개 전부 수정 없이 통과.
- **신규 unit test 2개**: 노이즈 문장(조사/동사/부사/자바스크립트 혼합)에서
  의미 있는 명사만 남는 것, `_get_kiwi`를 모킹해 kiwipiepy 없을 때 기존
  방식으로 정확히 대체되는 것(+`basis.keywords` 값 확인).
  `tests_v2`+`tests` **377 passed**(375 + 2).
- **실제 수집 데이터로 재검증**: 이미 수집해둔 2026-08 실데이터 project(4042
  고유 문서)에 새 `AnalyticsService`를 다시 돌려 TOP10을 재계산 — "폭염
  (1772)·지역(800)·기후(794)·충남(727)·정부(582)·현장(542)·농업(525)·
  대응(508)·발전(468)·전환(445)"으로 전부 실제 주제와 맞는 명사만 나왔다.
  이 재계산 결과로 `~/Desktop/AIPORG_2026-08/images/02_top10_keywords.png`
  를 직접 갱신했다(같은 프로젝트에 새 AnalyticsSnapshot과 TOP10 시각자료
  버전을 추가·승인 — 새 schema나 workflow 상태 없이 기존 repository
  메서드만 사용).
- 변경 파일: `app/analytics/service.py`,
  `docs/aiporg2/analytics.md`(키워드 산식 설명 갱신),
  `tests_v2/unit/test_analytics_service.py`. `app/visualization/service.py`는
  건드리지 않았다(입력이 바뀌었을 뿐 VIS-02/07 렌더링 로직은 그대로).

### ~~사용자가 결정할 사항(신규)~~ — 둘 다 사용자가 "이어서 처리"로 승인해 해결함(아래 절)

## 2026-10-19 22차: 텍스트 인코딩 복구 + documents.id 프로젝트 범위 지정

사용자가 "ㅇㅇ 이어서 처리"로 21차 끝에 남겨둔 미해결 사항 2개(인코딩 깨짐,
documents.id 충돌 가능성)를 모두 승인해 처리했다.

### 텍스트 인코딩 복구 (`app/collectors/transport.py`)

- **원인**: `requests`의 `response.text`는 HTTP `Content-Type` 헤더의
  charset만 신뢰하고(없으면 `text/*`에 RFC 기본값인 ISO-8859-1 적용),
  페이지 자체의 `<meta charset>` 선언은 전혀 보지 않는다. 일부 한국 뉴스
  사이트가 HTTP 헤더에 charset을 안 넣고 HTML 메타태그로만 선언해서 생긴
  문제(18차에서 4110건 중 15건, 약 0.4%로 보고된 것).
- **해결**: 이미 의존성에 있는 `beautifulsoup4`의 `UnicodeDammit`으로
  교체 — HTTP 헤더 → HTML meta charset → 인코딩 자동 감지 순으로 확인하는
  표준 도구. JSON 응답(네이버/다음/유튜브 API)에도 그대로 적용해도 안전함을
  확인(라이브 테스트: 올바른 UTF-8 JSON은 그대로 통과).
- **라이브 검증**: 18차에서 깨짐이 확인됐던 실제 URL
  (`mbn.co.kr/pages/news/newsView.php?news_seq_no=5210380`)을 수정된
  transport로 다시 가져와 "AI 농기계가 벼농사 '척척'" 같은 실제 한글이
  정상 디코딩되는 것을 직접 확인했다.
- `_default_request`를 직접 테스트하는 unit test가 이전엔 전혀 없었다(기존
  transport 테스트는 전부 `request_fn`을 주입해 우회) — `requests.request`를
  모킹하는 신규 테스트 3개 추가(헤더에 charset 없는 UTF-8 복구, HTML meta
  charset 우선 적용(EUC-KR), JSON 바디가 여전히 정상 파싱됨).
- `tests_v2`+`tests` **380 passed**(377 + 3).

### `documents.id` 프로젝트 범위 지정 (신규 마이그레이션)

- **원인**: 모든 collector의 `fetch()`가 `document_id = uuid5(NAMESPACE_URL,
  url)`로 URL만의 결정론적 해시를 계산한다(project_id 미포함) — 반면
  Evidence/Fact/Narrative의 ID 생성은 전부 이미 `project_id`를 해시 입력에
  포함하고 있었다(코드로 직접 확인). 그런데 `documents` 테이블의
  실제 PRIMARY KEY는 `id` 단독이라 테이블 전체에서 전역 유일해야 했다 —
  같은 URL을 다른 프로젝트(다른 달)가 재수집하면 충돌한다(21차 재검증
  중 실제로 겪음).
- **왜 안전한 수정인가**: `documents.id`를 참조하는 모든 FK(`DuplicateCluster.
  canonical_document_id`, `DocumentDuplicate.document_id`,
  `EvidenceDocument.document_id`)가 이미 전부 복합 FK
  `(project_id, id) -> (documents.project_id, documents.id)`로 선언돼
  있었다 — `documents.id` 단독의 전역 유일성에 의존하는 코드가 단 하나도
  없었다(코드 전체 grep으로 확인). 그래서 PRIMARY KEY를 `id` 단독에서
  `(project_id, id)` 복합키로 바꾸는 것만으로 충돌 없이 끝난다 — collector
  코드는 한 줄도 안 건드렸다.
- **신규 마이그레이션** `alembic_v2/versions/
  20261019_000002_scope_document_id_per_project.py`: SQLite는 PRIMARY KEY를
  제자리에서 못 바꾸고, Alembic의 `batch_alter_table`도 이름 없는 기존
  PK 제약을 못 찾아서(`drop_constraint(None, type_="primary")` →
  `ValueError: Constraint must have a name`, 라이브로 직접 겪음) 테이블을
  수동으로 재구성한다: rename aside → 새 PK로 재생성 → 데이터 복사 → 이전
  테이블 drop. **SQLite가 테이블 rename 시 다른 테이블의 FK 절을 자동으로
  새 이름 쪽으로 다시 써버리는 동작**(`duplicate_clusters` 등이
  `documents`가 아니라 방금 rename한 `documents_pre_v2`를 가리키게 됨)도
  라이브로 직접 겪어서 `PRAGMA legacy_alter_table=ON`으로 막았다 — 이
  pragma 없이 먼저 테스트해서 실패를 직접 재현한 뒤 고쳤다.
- **기존 모델도 함께 수정**: `app/models/document.py`의 `Document`가
  `UUIDPrimaryKeyMixin`(단일 `id` PK) 대신 명시적
  `PrimaryKeyConstraint("project_id", "id")`를 쓰도록 바꿨다 — 마이그레이션만
  고치고 Python 모델을 안 고치면 `Base.metadata.create_all()`을 쓰는
  대부분의 unit test가 여전히 구 스키마로 동작해 수정이 실제로 적용 안 된
  것처럼 보였을 것.
- **검증**: (1) 빈 DB에 upgrade/downgrade 양방향 라이브 테스트, (2) 실제
  행 데이터를 넣고 downgrade 후 데이터 보존·PK 원복 확인 후 재upgrade,
  (3) 같은 `document_id`를 **다른 두 프로젝트**에 실제로 insert해 더 이상
  충돌하지 않음을 라이브로 확인(수정 전에는 이 테스트가 바로 그 에러로
  실패하는 것도 먼저 재현함). (4) 기존 contract test
  (`test_sqlalchemy_metadata.py`의 `has_project_scoped_identity`)가
  `UniqueConstraint`만 인정하고 있어서 `PrimaryKeyConstraint`도 같은 의미로
  인정하도록 넓혔다(검증하려는 불변식 자체는 그대로 유지 — "같은
  (project_id, id)로 유일성이 보장되는가"는 PK로 보장해도 똑같이 참).
- 신규 unit test 2개(`test_sqlalchemy_repositories.py`에 repository 레벨
  교차 프로젝트 테스트, `test_migration_runtime.py`에 마이그레이션 레벨
  통합 테스트 — 둘 다 "같은 document_id를 다른 두 프로젝트에 insert해도
  안 터진다"를 직접 확인).
- `tests_v2`+`tests` **382 passed**(380 + 2).

## 2026-10-19 23차: TOP10 키워드 — 복합어 구절 병합

사용자가 7월 참고 보고서의 실제 "주요 키워드 TOP10" 카드 스크린샷을 보여주며
"주요 키워드가 단어로만 되는게 맞나"라고 질문. 비교해보니 참고본은 단일 명사
빈도표가 아니라 **복합어 구절**("집중호우", "AI반도체", "행정통합공론화")이고,
서로 다른 두 구절을 "·"로 묶어 보여주는 것("폭염·열대야")과 카테고리 태그
("재난/안전" 등)까지 있었다 — 요구사항 §4.4가 이미 "핵심 입력어와 새롭게
발견된 연관어를 구별... 정규화 규칙을 먼저 정한다"고 미해결로 남겨뒀던
부분이 실제로 이런 모습이었다.

범위를 3단계로 나눠 제시하고 사용자가 **1단계(인접 명사 합치기)만** 승인함
— 동시출현 짝짓기(2단계)와 카테고리 태그(3단계, 분류 체계를 새로 설계해야
하는 제품 결정)는 보류.

- **구현**: `_extract_keyword_tokens`가 (21차의) 단일 명사 추출 대신, kiwi
  토큰의 `.start`/`.len`으로 **공백·조사 없이 실제로 붙어 있는** 명사류
  토큰 구간을 하나의 구절로 합친다. 병합 허용 태그는 명사(NNG/NNP)·외국어
  (SL)·숫자(SN)·의존명사(NNB)·명사파생접미사(XSN)이고, 그 구간에 실제
  명사가 하나도 없으면 버린다 — 그래서 "것"/"수"/"때문"(NNB) 단독이나
  "123"(SN) 단독, 외국어 단독("AI", leaked "var")은 여전히 혼자서는 안
  뜨지만 "AI"+"반도체"처럼 명사에 바로 붙으면 "AI반도체"로 합쳐진다.
- **라이브로 검증한 뒤 구현**: 참고 카드의 문구를 실제 문장으로 만들어
  kiwi에 직접 돌려봄 — "집중호우"는 kiwi가 "집중"+"호우"로 쪼개고,
  "재난대응"도 "재난"+"대응"으로 쪼개지는 것을 먼저 확인한 뒤, 병합
  알고리즘이 이걸 다시 합치는지 전부 라이브로 검증하고서 코드에 반영했다.
  "균형성장"/"복지충남"은 kiwi 사전에 이미 통째로 등재돼 있어 애초에 안
  쪼개진다는 것도 확인함.
- **의도적으로 재현 안 한 것**: "취임1개월평가"/"공약이행로드맵" 같이
  참고본에서 공백 없이 붙어 있는 라벨은, 실제 기사 문장에서는 "취임
  1개월 평가"처럼 공백이 있을 가능성이 높아 자동 병합으로는 재현되지
  않는다 — 참고본 라벨이 손으로 다듬은 표기일 가능성이 높다고 보고,
  기계적으로 거기까지 맞추려 하지 않았다(사실과 다른 걸 억지로 만들지
  않음).
- 신규 unit test 1개(참고본 예시 문장으로 "집중호우"/"재난대응"/
  "ai반도체"/"행정통합"/"공론화"가 합쳐지는지, 서로 안 붙어있는 두 구절이
  하나로 잘못 합쳐지지 않는지 확인). 기존 테스트 전부(노이즈 제거, 기존
  fixture `{"정책":6,"지원":3}`, fallback) 수정 없이 그대로 통과 — 해당
  텍스트들은 합칠 대상이 공백으로 떨어져 있어 동작이 안 바뀜을 먼저 확인.
- `tests_v2`+`tests` **383 passed**(382 + 1). 실제 2026-08 수집 데이터로
  TOP10을 다시 계산해 `~/Desktop/AIPORG_2026-08/images/02_top10_keywords.png`
  갱신 — 자연스러운 기사 문장은 대부분 공백으로 띄어 쓰기 때문에 병합
  효과가 크게 드러나진 않았지만(폭염/충남/지역/정부 등 원래도 단일
  단어인 항목들), 노이즈 없이 전부 실제 의미 있는 단어/구절로 유지됨을
  확인했다.
- **범위 밖으로 남긴 것**: 동시출현 짝짓기("·"), 카테고리 분류 체계 —
  둘 다 추가 제품 설계 결정이 필요해 이번엔 진행하지 않았다.
