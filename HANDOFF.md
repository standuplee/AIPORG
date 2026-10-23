# AIPORG 공통 작업 인계

최종 정리: 2026-10-23. 작업 시작 시 실제 파일과 `git status`를 확인하고 사용자의 최신 요청을 우선한다. 이 문서는 현재 상태 요약이며, 과거 5~23차 상세 기록은 [구현 계획의 이관 기록](docs/superpowers/plans/2026-09-08-aiporg2-implementation.md#2026-10-19-인계-문서에서-이관한-상세-작업-기록)에 있다.

## 현재 목표와 구현 방향

현재 목표는 충남 전용 월간 보고서 도구를 범용 Issue Research & Analysis Engine으로 발전시키는 것이다. 사용자는 대상 지역, 기간, 핵심 이슈를 지정하고 시스템은 이슈별 조사·근거 검증·공개 반응 분석·월간 종합을 수행한다. 자동 이슈 발굴과 전수 여론 주장은 MVP 범위에서 제외한다.

정리 기준 branch는 `feat/issuescope-research-engine`이며 전용 worktree는 `/private/tmp/AIPORG-issuescope`다. 이 커밋에는 1.0 산출물/API 정리와 IssueScope 설계·계획만 담는다. 기능 구현은 이 기준 branch에서 새로 분기할 `feat/issuescope-implementation`에서 시작한다. 원래 worktree의 `feat/issue-driven-research`와 미커밋 변경은 보존한다. 저장소별 설계는 [IssueScope design](docs/superpowers/specs/2026-10-23-issuescope-engine-design.md), 구현 계획은 [IssueScope plan](docs/superpowers/plans/2026-10-23-issuescope-engine.md)이다.

## 1.0 정리

- 재생성 가능한 `output_live/`, `output_naver/`, `output_youtube/` 산출물과 사용되지 않던 커뮤니티·YouTube FastAPI 앱을 제거했다. FastAPI/Uvicorn도 의존성에서 삭제했다.
- README와 1.0 CLI 예시의 존재하지 않던 2026-03 fixture 경로를 2026-06 설정으로 수정했다.
- 기능 구현 branch에서는 기존 2.0을 IssueScope 기반으로 발전시킨다. 원래 worktree와 미커밋 변경은 별도로 유지한다.

## 확정된 결정

- 사용자가 매월 입력한 키워드 목록만 검색어로 쓴다. 고정 지역·기관·인물 조사어는 추가하지 않는다.
- 댓글을 포함한다. 현재 네이버·유튜브 댓글 수집이 구현됐으며 analytics는 본문과 댓글을 분리 집계한다.
- LLM은 Narrative 계층에서 API로 호출한다. 현재 Gemini 어댑터의 기본 설정은 `gemini-2.5-flash`; UI는 키 부재·호출 실패 시 템플릿으로 대체한다. GPT·Claude 어댑터는 미구현이다.
- UI는 로컬 Streamlit이다. 서술·시각자료 수정 이력과 승인은 Repository를 통해 저장한다.
- 커뮤니티는 클리앙·디시인사이드·펨코·루리웹·더쿠이며 현재 `config/community.yaml`에서 모두 활성화되어 있다. robots.txt·요청 제한을 적용하고 펨코는 허용 게시판 범위로 제한한다. X·인스타그램은 현재 범위 밖이다.
- HWPX는 `python-hwpx==6.8.0`을 사용한다. 보고서 구성은 AIPORG에 두고 라이브러리 자체 수정이 필요하면 별도 fork로 전환한다. 로컬 clone 이력은 있지만 GitHub fork는 만들지 않았다.
- TOP10은 형태소 기반 빈도와 실제로 붙어 있는 명사류 구절 병합까지 구현한다. 동시출현 짝짓기와 카테고리 분류는 보류한다.
- 새 schema·workflow 상태를 임의로 추가하지 않는다. 추가 계약이 필요하면 설계 결정부터 한다.

## 현재 구현 상태

- 수집 → 정제·중복 제거 → Evidence → Fact/Issue → Analytics → 서술 생성·수정·승인 → 시각자료 승인 → Report 생성 → HWPX 시제품 다운로드가 UI에 연결됐다.
- 네이버·다음·유튜브·구글·커뮤니티 수집기, 키워드×채널 배치 workflow가 있다. 같은 프로젝트에서는 수집을 한 번만 실행하며 재수집은 새 프로젝트로 진행한다.
- 기사 본문은 `trafilatura`로 추출하고 transport에서 인코딩을 복구한다. `documents` PK는 `(project_id, id)`이며 같은 URL을 다른 프로젝트에서 저장할 수 있다(22차 migration).
- 이슈는 근거 문서의 수집 키워드 기준으로 그룹화한다. 통계는 canonical 문서와 문서 ID 근거를 사용한다. **문서/채널 단위 감성 집계**(AnalyticsService)는 여전히 기존 metadata 라벨만 세고 미지정은 미분류다 — 이건 안 바뀜. 비교기간 데이터가 없으면 증감률을 만들지 않는다.
- **통계 집계는 이제 별도 OS 프로세스에서 백그라운드로 실행된다**(`app/analytics/jobs.py::AnalyticsJobManager`, spawn 방식, 서버 프로세스당 1건, DB 파일 단위 `fcntl.flock`로 중복 실행 차단). Streamlit UI는 `st.json(snapshot.metrics)`로 전체 metrics를 더 이상 렌더링하지 않는다 — 실데이터에서 수 MB·최대 46,542 키워드로 브라우저 탭이 죽던 문제의 원인이었다(2026-10-19 기록). 대신 SQLite JSON1(`json_extract`/`json_each`)로 SQL에서 상한을 건 요약만 Python으로 가져온다(`AnalyticsRepository.get_latest_summary`, 상위 30개, 키 300자 상한). 문서 목록도 `DocumentRepository.list_canonical_page`로 50건씩 페이지네이션한다(body/metadata는 조회하지 않음).
- **이슈 세부(subissue) 단위 감성·입장은 이제 실제로 분류된다**(`app/sentiment/service.py`, 사전 기반, 네트워크·LLM 없음). 감성(긍정/부정/중립/혼재)과 입장(찬성/반대/중립/혼재/해당없음)은 서로 다른 축으로 별도 분류하며, 이전엔 전부 고정 NEUTRAL/NOT_APPLICABLE이었다. `NarrativeContext.positive_reasons`/`negative_reasons`도 이제 분류된 fact 요약으로 실제로 채워진다(최대 5개, 부족하면 있는 만큼만 — 채우려고 지어내지 않음).
- 서술은 프로젝트 단위 버전이다. 이슈를 달리 선택해 생성하면 같은 프로젝트의 새 버전으로 저장된다.
- 시각자료는 VIS-02 채널 비중·VIS-07 TOP10만 구현됐다. 표시 항목 편집·버전 저장·개별 승인을 지원한다.
- 최종 승인 서비스는 최신 서술과 필수 시각자료의 승인 여부를 확인한다. HWPX writer는 표지·목차·요약의 3쪽 구성 시제품이다. 전체 보고서·DOCX·Markdown writer는 아직 없다.

## 남은 제약과 다음 행동

1. **승인 당시 출력 버전 고정이 우선이다.** `app/report/approval.py`는 승인 시 Report를 만들지만 승인된 서술·시각자료 출력 버전 전체를 고정하지 않는다. `streamlit_app/console.py::page_output`은 최신 출력을 다시 읽으며 승인 후 수정본의 재승인을 재검사하지 않는다. 승인본 번들 계약과 출력 게이트를 정리하고 회귀 테스트를 추가해야 한다. 이번 검토에서는 발견·문서화만 했다.
2. HWPX 시제품을 실제 한컴에서 열어 쪽수·줄바꿈·표 넘침을 확인한다. 기존 자동 검증은 패키지/스키마 검증이며 실제 편집기 검증을 대체하지 않는다. 원본 HWPX·표지 사진·로고 확보 여부도 미결정이다.
3. 나머지 VIS 종류와 일반 표 편집, 원자료 변경에 따른 본문 갱신, 전체 월간 HWPX 조립, 동일 승인본 DOCX·Markdown을 구현한다.
4. 2.0 블로그 수집기 범위를 정한다. 구글 결과를 모두 NEWS로 분류하는 단순화, 댓글을 Evidence→Fact→Issue에도 포함하는 현재 동작, 공식 출처 목록/정책도 보완 대상이다. 현재 UI는 공식 출처 목록을 전달하지 않는다.
5. 비교기간 수집의 충분성, 사이트별 실제 수집 가능 범위, API 예산을 운영 시 확인한다. 설정의 활성화는 수집 완전성을 의미하지 않는다.
6. 복합어 TOP10의 동시출현 짝짓기·카테고리 분류는 별도 결정 전 구현하지 않는다. Document/Evidence의 세부 version lineage도 보류 상태다.
7. 감성/입장 분류는 작은 통제 어휘 사전 기반 baseline이다(1.0 `aiporg/analyze/sentiment.py` 포팅·확장). 1.0에 있는 LLM 배치 분류기(`aiporg/llm/sentiment_llm.py`, 사전 폴백 포함)는 아직 포팅하지 않았다 — 정확도를 높이려면 그게 다음 후보다. "주요 원인" 묶기는 지금 fact 단위 그대로이며, 참고 PDF처럼 여러 근거를 하나의 원인으로 요약하는 건 안 한다.

## 실행과 검증

Python 3.12 기반 `.venv`에 `requirements-dev.txt`를 설치하고 `.env.example`을 참고해 2.0 키를 설정한다. `.env` 내용을 인계 문서에 기록하지 않는다.

```bash
./.venv/bin/streamlit run streamlit_app/console.py --server.address 127.0.0.1
# 접속: http://127.0.0.1:8501

./.venv/bin/python -m pytest tests_v2 tests -q
```

앱이 시작 시 Alembic migration을 적용한다. 기본 DB는 `aiporg2.db`이고 환경변수 변경 후 프로세스를 재시작해야 한다. 상세 설치 명령은 [README](README.md#빠른-시작--streamlit-ui)에 있다.

전체 테스트 결과는 **417 passed**다.

## 직전 완료 작업: 통계 집계 백그라운드 실행 + 사이드바 진행 표시

- 사용자 요청: 통계 집계 시 브라우저 탭이 메모리 부족으로 종료·새로고침됨 → 백그라운드 실행 + 사이드바 진행 표시 요청. 복합 검색어가 모든 단어 포함 조건인지도 질문.
- 원인: `page_analytics`가 `IssuesToAnalyticsWorkflow.run()`을 Streamlit 프로세스 안에서 동기 실행하고 `st.json(snapshot.metrics)`로 전체 metrics를 렌더링했다. 실데이터 기준 metrics JSON이 3.8~8.1MB, 최대 46,542 키워드·124,774 근거 참조였다.
- [사전 합의된 설계](docs/superpowers/specs/2026-10-19-analytics-background-design.md)대로 구현: 새 schema/DB 테이블 없이 기존 repository/workflow만 사용(AGENTS.md 1·3 준수).
  - `app/repositories/sqlalchemy.py`: `SqlAlchemyAnalyticsRepository.get_latest_summary()`(SQLite `json_extract`/`json_each`로 SQL에서 상위 30개·300자 상한까지 걸러 반환, 전체 metrics 컬럼은 절대 SELECT하지 않음), `SqlAlchemyDocumentRepository.count_canonical()`/`list_canonical_page()`(50건 상한, body/metadata 미조회), `SqlAlchemyEvidenceRepository.count_by_project()`. 세 Repository 프로토콜에도 동일 시그니처 추가.
  - `app/analytics/jobs.py`(신규): `AnalyticsJobManager` — `multiprocessing`(spawn)로 집계 1건을 별도 프로세스에서 실행, 진행 상황은 throttled(0.2초)된 `Queue` IPC로 전달, 부모 프로세스 종료 감지로 좀비 방지, DB 파일 단위 `fcntl.flock`으로 다른 서버 프로세스와의 중복 실행도 차단. 작업자 프로세스는 자체 DB 세션을 만들며 ORM 세션이나 Streamlit 객체가 프로세스 경계를 넘지 않는다.
  - `streamlit_app/analytics_ui.py`(신규): 사이드바 진행 상태, 제한된 요약, 페이지네이션 문서 표 렌더링 — 순수 렌더 함수만 두고 폴링·제출은 `console.py`가 호출.
  - `streamlit_app/console.py::page_analytics`: "통계 집계 실행" 버튼이 `manager.submit()`으로 작업을 제출하고 즉시 반환(동기 대기 없음). `st.json(snapshot.metrics)` 전체 렌더링을 제거하고 `get_latest_summary()` 기반 요약으로 교체. 고유 문서 목록을 전수 조회에서 50건 페이지네이션으로 교체. `main()`에 `st.fragment(run_every=3)` 사이드바 상태 위젯 추가(페이지 이동·새로고침 후에도 같은 서버의 작업 상태 유지). "2. 수집 설정·실행"의 키워드 입력 캡션에 복합 검색어가 AND 조건을 보장하지 않는다는 안내를 추가(코드 확인: 각 줄 전체를 그대로 `query`/`q` 파라미터로 전달, AIPORG 자체의 전체-단어-포함 필터는 없음).
- 테스트: `tests_v2/unit/test_analytics_ui_queries.py`(bounded SQL 검증, 3건), `tests_v2/unit/test_analytics_jobs.py`(프로세스/IPC/락 머신 7건, 모듈 레벨 fake worker 필요 — spawn은 타겟을 import 참조로 pickle), `tests_v2/integration/test_analytics_jobs_integration.py`(실제 spawn 프로세스로 Alembic 마이그레이션된 임시 SQLite에 커밋/롤백 검증, 2건), `tests_v2/unit/test_analytics_ui.py`(`AppTest.from_function` 렌더 함수 7건 — 이 함수는 대상 함수의 소스만 재실행하고 모듈 전역(import, 상수)은 안 가져오므로, 테스트 래퍼가 자체적으로 import하도록 작성). 전체 `tests_v2`+`tests` **417 passed**(409 + 7 UI, 통계 집계 전용 테스트는 409건에 포함).
- 다음 행동(결정 필요 없으면 보류): 실제 브라우저에서 긴 집계를 돌려 사이드바 갱신 체감 확인(자동화 테스트는 UI 함수 단위까지만 검증했고 실제 브라우저 메모리 개선을 직접 재현하지는 않았다). `AnalyticsJobManager`는 서버 프로세스당 1건만 허용하므로 여러 프로젝트를 동시에 집계할 수 없다 — 필요해지면 재설계 대상.

## 기능 완료 시 커밋·푸시 규칙
- 기능 단위의 구현과 필요한 테스트가 완료되면 `HANDOFF.md`를 최신 상태로 갱신한 뒤 해당 기능의 변경만 선별하여 커밋하고 원격 브랜치에 푸시한다.
- 커밋 전 `git status`와 diff를 확인한다. 다른 작업자의 변경, 무관한 파일, 비밀값은 포함하지 않는다. 테스트가 실패하거나 기능이 미완성이면 완료 커밋으로 처리하지 않고 상태를 `HANDOFF.md`에 기록한다.
- 커밋 메시지는 `<type>(scope): <subject>` 형식을 사용한다. `scope`는 변경 영역을 나타내며 필요 없으면 생략할 수 있다. 제목은 변경 내용을 짧고 구체적으로 설명한다.
- 타입은 `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore` 중 변경 성격에 맞게 선택한다. 설명이 필요한 경우에만 본문을 쓰고, 관련 이슈가 있을 때만 푸터를 쓴다.
- 커밋 메시지에 `commit by Claude`, `Co-authored-by`, 도구 이름, 자동 생성 문구를 넣지 않는다. 변경 내용에 필요한 메시지만 작성한다.
- 푸시가 실패하면 강제 푸시하지 않는다. 실패 원인과 커밋 상태를 `HANDOFF.md`에 기록하고 충돌을 확인한다.
