# AIPORG 공통 작업 인계

최종 정리: 2026-10-23. 작업 시작 시 실제 파일과 `git status`를 확인하고 사용자의 최신 요청을 우선한다. 이 문서는 현재 상태 요약이며, 과거 5~23차 상세 기록은 [구현 계획의 이관 기록](docs/superpowers/plans/2026-09-08-aiporg2-implementation.md#2026-10-19-인계-문서에서-이관한-상세-작업-기록)에 있다.

## 현재 목표와 구현 방향

새 PRD 기준 재구성 작업은 `issue-driven-research-engine` 브랜치에서 진행한다. 기존 AIPORG 2.0 구현을 공통 기반으로 보유하며, 제품 요구사항의 기준은 저장소 루트 [PRD.md](PRD.md)다. 현재 첫 구현 단위는 Qwen으로 이슈별 조사 질문과 연결 검색어를 만드는 것이다. 기존 2.0의 마지막 기록된 전체 테스트 결과는 **431 passed**이며 이번 변경에서는 전체 테스트를 다시 실행하지 않았다.

제품 목표는 사용자가 대상·기간·핵심 이슈를 지정하고, 시스템이 이슈별 조사·근거 검증·공개 반응 분석·월간 종합을 수행하는 범용 Issue Research & Analysis Engine이다. 자동 이슈 발굴과 전수 여론 주장은 MVP 범위에서 제외한다.

PRD는 사용자 지정 이슈별 반복 조사, Fact와 Evidence의 추적성, Fact Research와 공개 검색 기반 Opinion Analysis 분리, 이슈별 결과의 월간 합성 및 출처 포함 보고서를 요구한다. 기존 월별 키워드 수집·분석, 서술 검수·승인, HWPX 시제품은 재사용 가능성을 조사할 기존 2.0 기능이며 PRD 전체 요구를 이미 충족한다는 뜻은 아니다. 기존 보고서 기준은 [7월 월간 보고서 요구사항](docs/aiporg2/monthly-keyword-report-requirements.md)이다.

## PRD 검토 및 현재 작업 상태 (2026-10-23)

- 새 브랜치에 루트 `PRD.md`를 두고 source of truth로 삼는다. 문서는 80개 절로 제품 경계, MVP 요구사항, 데이터/서비스/API 제안, 구현 단계, 수용 기준 및 Definition of Done을 정의한다. 원칙은 “사용자가 이슈를 정하고 AI가 조사”하는 것이며 자동 이슈 발굴이나 전수 SNS 수집은 MVP 범위가 아니다.
- Qwen 첫 연결: 로컬 Ollama의 `qwen3:8b`를 `/api/chat`으로 호출한다. 역할 프롬프트는 [prompts.py](app/research/query/prompts.py)의 `SYSTEM_PROMPT`다. `QueryExpansionResult` JSON Schema를 전달하고 조사 질문과 검색어를 각각 최대 10개로 제한하며 모든 질문이 하나 이상의 검색어에 연결되는지 검증한다. Qwen3의 느린 thinking 응답을 피하기 위해 `think: false`를 지정한다.
- 로컬 Swagger 확인: [api.py](app/research/api.py)에 `POST /query-expansion`을 추가했다. 기존 `IssueInput`을 요청 모델로 재사용하며 Swagger 예시에 `충청남도 / 2026-09-01~2026-09-30 / 삼성디스플레이 67조 투자`를 표시한다. 실행은 `./.venv/bin/uvicorn app.research.api:app --host 127.0.0.1 --port 8000`, 접속은 `http://127.0.0.1:8000/docs`다. Ollama 연결 실패나 생성 오류는 502로 반환한다.
- 이번 변경 파일: `app/research/api.py`, `requirements.txt`, `tests_v2/integration/test_query_expansion_api.py`, `HANDOFF.md`. 기존 미커밋된 PRD/Qwen 작업 파일은 함께 stage하지 않았다.
- 검증: API 통합 테스트 **1 passed**, Qwen 서비스 단위 테스트 **4 passed**, `git diff --check` 통과. Uvicorn을 로컬 실행하고 예시 JSON을 실제 Ollama `qwen3:8b`에 보내 HTTP 200 및 질문 10개·검색어 10개 응답을 확인한 뒤 서버를 종료했다. 테스트 환경에서 Starlette의 `httpx` 사용 deprecation 경고가 1건 나온다.
- Qwen 연결 단계 파일: `app/research/query_expansion.py`, `app/research/query/`, `app/schemas/research.py`, `tests_v2/unit/test_qwen_query_expansion.py`. 이 파일들은 이번 Swagger 변경 전에 작업 트리에 있던 상태다.
- 검증: 지정 단위 테스트 `tests_v2/unit/test_qwen_query_expansion.py` **4 passed** 및 `git diff --check` 통과. 설치된 `qwen3:8b`에 예시 이슈를 보내 실제 생성 결과 질문 10개·검색어 10개, 미연결 질문 0개를 확인했다(약 66초). 외부 API는 호출하지 않았다.
- Qwen 2단계 분리(2026-10-24): `expand()`는 Qwen #1(`ResearchPlan`: decomposition + 질문 11개, 검색어 없음) → Qwen #2(`QueryDraftSet`: 질문당 검색어 2~3개) 순으로 호출한다. 코드가 담당하는 부분: `protected_terms`(이슈 원문 토큰), `REGION_ALIASES` 충청남도/충남 변형 확장, 방향성 단어(`BIAS_TERMS`) 제거(CONCERN 제외), REACTION의 중립 검색어(`OPINION_CORPUS`) 생성. `SearchQuery.purpose`(자유 문자열)를 `search_purpose: SearchPurpose`(FACT_RESEARCH/OPINION_CORPUS/FRAME_DISCOVERY)로 교체. 질문 본문에 남는 "창출" 등은 제거하지 않았다. 단위 테스트·API 테스트 6 passed, 실제 qwen3:8b 2회 호출로 질문 11개/검색어 57개 확인.
- 검색 provider(2026-10-24): `app/search/`에 `SearchProviderBase`(search(query, channel, limit, sort="accuracy|recency")), Naver(NEWS/WEB/BLOG)·Daum(WEB/BLOG/CAFE) provider, `SearchService`(search_fact/search_opinion을 분리, 엔진 하나가 실패해도 나머지 반환하고 경고 로그), URL+정규화 제목 dedup을 추가했다. 키는 기존 `AIPORG2_*` 환경변수를 쓴다. `app/research/api.py`에 `GET /search/fact`, `/search/opinion`을 붙였다. 새 `SearchResult`는 `app/search/schemas.py`에 있어 `app/schemas/document.py`의 동명 모델과 다르다. 미구현: 검색 캐시, 기간 필터, Google provider(cx 없음, 403), 기사 본문 fetch. 단위 테스트 `tests_v2/unit/test_search_service.py`.
- 검색 결과 분석 V2(2026-10-24): 이슈 독립 구조. `IssueDecomposition`에 persons/dates/laws/projects 추가, `config/source_registry.yaml`(도메인→SourceType), `app/search/signals.py`(출처·숫자/날짜 언급·구조적 노이즈를 코드로 산출), `app/search/analyzer.py`(Research Question 기준 Qwen 0~3점 평가, 5건 배치, 누락 id 재요청, matched_terms/discovered_entities를 코드가 제목·스니펫 기준으로 정제). fetch 후보는 점수≥2이고 OUT_OF_PERIOD가 아닌 것(BACKGROUND 질문은 과거 자료 허용). 4개 이슈 회귀(삼성/공공기관 이전/석탄화력 특별법/폭염, 각 RQ01만, 6~7분): 삼성은 점수가 3에 쏠림(19/23), 나머지는 0~3으로 분산되고 나무위키·PDF 노이즈는 낮게 평가됨. 미검증: 같은 문서의 RQ별 점수 차이, 이슈 기간(삼성 외 8~9월은 가정). 다음: Article Fetcher.
- 필수 흐름은 이슈별 검색 계획 → 검색 및 실제 문서 읽기 → Evidence에 연결된 Fact → 정보 공백 판단과 예산 내 반복 검색 → 공개 반응의 채널/대상/감성/프레임/이유 분석 → 이슈·월간 종합 및 출처 추적 가능한 보고서다. 검색 가능한 공개 콘텐츠를 전체 여론으로 표현하지 않고, snippet만으로 VERIFIED Fact를 만들지 않는다.
- 저장소의 사용자 지침을 계속 적용한다: 임의 schema 금지, 기존 Pydantic 모델 이름 유지, Repository 밖 DB write 금지, Collector의 LLM 호출 및 Analyzer의 웹 요청 금지, Writer의 신규 Fact 생성 금지, Evidence 없는 수치 금지. 각 모듈 변경에는 단위 테스트를 작성하고 통합 테스트 실패 시 다음 기능으로 넘어가지 않는다. PRD의 제안은 이 지침을 무효화하지 않는다.
- 기존 2.0은 Streamlit, SQLite/SQLAlchemy, Repository, Collector, Evidence/Fact, Analytics, Narrative 및 Report 기반을 갖고 있다. PRD §63·§75는 FastAPI/PostgreSQL을 제안하지만, PRD §77은 먼저 기존 구조와 관례를 조사하도록 한다. 이전 [설계 초안](docs/superpowers/specs/2026-10-23-issuescope-engine-design.md)은 FastAPI/PostgreSQL 도입을 배제하고 기존 UI/DB 재사용을 제안해 PRD와 충돌한다. 이 초안과 [구현 계획](docs/superpowers/plans/2026-10-23-issuescope-engine.md)은 구현 승인이나 최신 결정이 아니며, 구현 전 PRD 및 사용자 지침 기준으로 재검토·수정해야 한다.
- 기존 2.0의 `Issue`는 근거 기반 분석 그룹이다. 사용자 입력 Research Issue와 같은 개념이라고 간주하지 않는다. PRD 구현 시 기존 모델명과 저장/워크플로 경계를 확인하고, 구체 schema 변경은 사용자 지침을 만족하는 설계가 확정된 뒤에만 진행한다.
- 다음 행동: 생성된 검색어를 검색 provider에 전달하고, 수집 결과를 근거 기반 Fact pipeline에 연결한다. UI 연결과 반복 조사 루프는 아직 구현하지 않았다.
- PRD 검토 당시 이력: `PRD.md`를 새 브랜치에 복사하고 내용 일치 및 문서 diff를 확인했다. 당시에는 코드·schema·테스트 변경이 없었고 기능 구현도 시작하지 않았다.

## 1.0 정리

- 재생성 가능한 `output_live/`, `output_naver/`, `output_youtube/` 산출물과 사용되지 않던 커뮤니티·YouTube FastAPI 앱을 제거했다. FastAPI/Uvicorn도 의존성에서 삭제했다.
- README와 1.0 CLI 예시의 존재하지 않던 2026-03 fixture 경로를 2026-06 설정으로 수정했다.
- 새 `issue-driven-research-engine` branch는 이 기준에서 PRD 기능을 구현한다.

## 1.0 정리 검토 (2026-10-23)

- 사용처와 진입점을 확인했다. CLI·보고서·분석·수집 코드에는 테스트와 내부 연결이 있다. 설정·예제 데이터는 보존하고, 사용자 승인에 따라 재생성 가능한 `output_live/`, `output_naver/`, `output_youtube/` 결과물은 삭제했다.
- 저장소 내 호출자가 없던 커뮤니티 API와 YouTube 분석 API를 사용자 승인에 따라 삭제했다(`aiporg/api/`, `aiporg/youtube/api.py`). FastAPI/Uvicorn도 다른 코드에서 사용되지 않아 `requirements.txt`에서 제거했다.
- 2.0은 YouTube 영상·댓글 수집을 지원하고 공통 Analytics에서 채널/이슈/키워드 단위로 집계한다. 1.0의 YouTube 전용 토픽·감성·특이동향·요약 분석은 아직 포팅하지 않았다.
- README와 `aiporg/cli.py` 사용 예시가 저장소에 없는 `config/chungnam_202603.yaml`을 가리키던 오류를 실제 fixture 설정인 `config/chungnam_202606.yaml`로 고쳤다.
- 다음 후보: YouTube 전용 API 대신 2.0의 공통 수집·분석·UI에 영상 통계(조회·좋아요)와 영상/댓글을 구분한 이슈·감성 분석을 보강한다. 범위와 화면 설계는 구현 전 확정해야 한다.
- 변경 파일: `README.md`, `aiporg/cli.py`, `HANDOFF.md`, `aiporg/api/`, `aiporg/youtube/api.py`, `aiporg/youtube/__init__.py`, `requirements.txt`, 그리고 위의 세 `output_*` 디렉터리. 전체 테스트에서 API/CLI 관련 회귀를 함께 확인했다.

## 서술 보고서 레이아웃 정리 (2026-10-23)

- 이슈별 초안을 배경·경과 문장, 핵심 과제 표, 근거 출처, 해석 문장 순서로 보여준다. Gemini 응답은 `overview`/`closing` 두 영역으로 받고 문장마다 기존 근거 ID 검증을 유지한다. 템플릿 fallback은 실제 하위 쟁점 감성 건수만 요약한다.
- Narrative 버전에 `issue_id`를 저장해 선택한 이전 버전도 이슈 맥락과 함께 렌더링하며, 레거시 버전은 기존 글머리표 화면으로 표시한다. 온라인 반응 별점은 근거 없는 비율 산식을 만들지 않고 고정 감성 매핑을 쓴다.
- 변경에는 Narrative UI, schema, Gemini adapter, Repository, 단위·통합 테스트가 포함된다. 전체 `tests_v2` + `tests`: **431 passed**. 통합 Streamlit 검증은 임시 `XDG_CACHE_HOME`/`MPLCONFIGDIR` 지정으로 폰트 캐시 권한 문제를 피했다.

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

2026-10-19 백그라운드 집계 변경 시점의 전체 테스트 결과는 **417 passed**였다. 이후 서술 보고서 레이아웃 작업에서 **431 passed**가 기록됐다. 이 수치는 모두 과거 실행 결과다.

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

## 이전 검토: 사용자 지정 이슈 기반 조사 엔진 (2026-10-20)

- 최신 목표: 사용자가 기간·지역·핵심 이슈를 정하고 AI가 이슈별 검색 확장·반복 조사·검증·공개 반응 분석·월간 종합을 수행한다. 자동 이슈 발견·전체 뉴스 클러스터링·이슈 중요도 선정은 현재 목표에서 제외하며 이전 검토의 해당 우선순위는 철회한다.
- 완료: Issue Research / Opinion Analysis / Report Synthesis 기준으로 현행 2.0 코드를 정적 비교했다. 기존 검색어별 이슈 구성이 출발점에는 가깝지만, 확장 검색어 여러 개를 원래 사용자 이슈에 연결하는 계약이 필요하다.
- 부족한 기능: 쿼리 생성 LLM·미확인 정보 판별·반복 수집·조사 종료 예산이 없다. workflow는 일방향이며 프로젝트 수집은 한 번만 실행한다. Fact는 앞 500자 근거의 첫 문장·기사 발행일에 의존하고 검증은 출처 수/공식 여부 중심이다. 반응 대상·프레임·이유 분석, 여러 이슈의 월간 종합, 승인본 고정도 보완 대상이다.
- 결정/다음 행동: 구현 착수 아님. 이슈↔검색어 연결과 한 이슈의 제한된 반복 조사부터 설계할 것을 권한다. 기존 Collector·Repository·본문 추출·승인 UI는 재사용한다. 기존 ‘입력 검색어만 사용’은 현행 구현이며 최신 목표는 사용자 지정 이슈 안에서 확장하는 방식이다. LLM을 Narrative에만 두던 배치도 설계 대상이지만 Collector LLM 호출·Analyzer 웹 요청 금지는 유지한다. 새 schema/상태는 임의 추가하지 않는다.
- 변경/검증/막힌 점: 이번 변경은 `HANDOFF.md`뿐이다. 기존 미커밋 구현은 유지했다. 테스트·실수집·외부 사실확인은 수행하지 않았고 기존 417 passed는 이번 검증 결과가 아니다.

## 기능 완료 시 커밋·푸시 규칙
- 기능 단위의 구현과 필요한 테스트가 완료되면 `HANDOFF.md`를 최신 상태로 갱신한 뒤 해당 기능의 변경만 선별하여 커밋하고 원격 브랜치에 푸시한다.
- 커밋 전 `git status`와 diff를 확인한다. 다른 작업자의 변경, 무관한 파일, 비밀값은 포함하지 않는다. 테스트가 실패하거나 기능이 미완성이면 완료 커밋으로 처리하지 않고 상태를 `HANDOFF.md`에 기록한다.
- 커밋 메시지는 `<type>(scope): <subject>` 형식을 사용한다. `scope`는 변경 영역을 나타내며 필요 없으면 생략할 수 있다. 제목은 변경 내용을 짧고 구체적으로 설명한다.
- 타입은 `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore` 중 변경 성격에 맞게 선택한다. 설명이 필요한 경우에만 본문을 쓰고, 관련 이슈가 있을 때만 푸터를 쓴다.
- 커밋 메시지에 `commit by Claude`, `Co-authored-by`, 도구 이름, 자동 생성 문구를 넣지 않는다. 변경 내용에 필요한 메시지만 작성한다.
- 푸시가 실패하면 강제 푸시하지 않는다. 실패 원인과 커밋 상태를 `HANDOFF.md`에 기록하고 충돌을 확인한다.
