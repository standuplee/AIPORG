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
