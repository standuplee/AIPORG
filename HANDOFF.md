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
- Fact Research V1(2026-10-25): 문서별 평가·claim 추출은 과하다고 판단해 삭제하고 `app/search/fetcher.py`(requests→trafilatura, JSON-LD/메타/time/본문 패턴 날짜 복구, `published_at_source` 기록), `app/search/html_meta.py`, `app/search/synthesizer.py`(공식 출처 우선 최대 8문서×3000자를 Qwen 한 번에 종합 → `FactResearchResult`: summary/key_facts/timeline/current_status/기관·인물·장소/uncertainties/missing_information, 사실당 근거 최대 2개)로 대체했다. Qwen 호출은 `num_ctx=24576`, 타임아웃 600초. 삼성 실측 127초, 요약·상태·출처 연결 합격 수준이나 timeline 날짜 누락, 2027년 2월 착공 누락, uncertainties에 일반 추측 1건 남음. 나머지 3개 이슈는 이전 설정(1500자)으로만 돌렸고 v2 미실행. 다음: Opinion Research. 검색 Analyzer V2는 더 튜닝하지 않는다.
- Opinion/Report V1(2026-10-25~26): 온라인 자료를 두 층으로 나눈다. (A) 논점(Discussion): 관련 글 전체(정책·기사 포함)에서 Qwen이 논점 이름을 제안하고, 코드가 논점 단어를 실제 포함한 글만 근거로 재산정(2건 미만·이슈 자체·80% 이상 중복·거의 모든 글이 언급하는 논점은 제거). 기대·우려를 말하지 못한다. (B) 반응(Reaction): 1차 Qwen 판정+근거 구절 → 코드가 인용 존재만 확인 → 2차 Qwen 확인 → 후보. 반응은 사람이 승인한 것만 ReactionTheme·여론 표정에 쓴다. 자동 승인 모드는 정밀도가 낮아(폭염 11건 중 1건, 석탄화력 12건 중 4~5건) 보고서에 쓰지 않는다. 검토 화면 `streamlit_app/opinion_review.py`(`./.venv/bin/streamlit run ...`, 세션 `output/research/session_*.json`): 1) 논점 후보(기본 선택, 해제 가능) 2) 반응 후보(기본 미검토, 전부 사용/제외 결정해야 분석 버튼 활성화). 보고서 `app/research/report.py`는 "주요 논점"과 "여론 표정"을 분리하고, 반응 0건이어도 논점 섹션은 채우며 시사점은 사실·논점 기반 관리 포인트만 쓴다. 석탄화력 논점은 경제 충격·고용 전환·재정 지원·정의로운 전환·통합본사·탈석탄 원칙 논란이 잡히고, 폭염은 쉼터 확대·기후살인 프레임·인명피해·AI·드론(취약계층은 누락), 삼성은 투자 규모·MOU·부동산·인프라가 잡힘. 미해결: 논점 요약이 "~했다는 내용을 다룬다" 꼴로 사실처럼 읽히는 경우가 있음, 반응 근거 구절이 사실 문장인 경우(석탄화력 성명서), 모든 판정이 로컬 qwen3:8b이며 실행마다 달라짐. 다음: 실제 검토 화면으로 세 이슈를 검토해 보고 반복해서 제외하는 유형이 보이면 후보 생성 개선.
- 반응 표본 단계 분리(2026-10-26): 반응 0건=논점 정상·'반응 부족'·톤 판단 없음, 1~2건=확인된 반응 원문 그대로 표시·톤 '판단 어려움'·시사점은 사실+논점 기반만, 3건 이상=테마·톤 분석. 채널별 특징은 채널 안의 글 3건 이상이 뒷받침하는 논점으로 구성(`ChannelInsight.discussion_topics`), 반응 방향은 반응 3건 이상일 때만 덧붙임. 다음: 세 이슈 처음부터 최종 회귀(검토 화면 거쳐 보고서 비교) 후 분석 V1 종료, 그다음 Streamlit 통합.
- 필수 흐름은 이슈별 검색 계획 → 검색 및 실제 문서 읽기 → Evidence에 연결된 Fact → 정보 공백 판단과 예산 내 반복 검색 → 공개 반응의 채널/대상/감성/프레임/이유 분석 → 이슈·월간 종합 및 출처 추적 가능한 보고서다. 검색 가능한 공개 콘텐츠를 전체 여론으로 표현하지 않고, snippet만으로 VERIFIED Fact를 만들지 않는다.
- 저장소의 사용자 지침을 계속 적용한다: 임의 schema 금지, 기존 Pydantic 모델 이름 유지, Repository 밖 DB write 금지, Collector의 LLM 호출 및 Analyzer의 웹 요청 금지, Writer의 신규 Fact 생성 금지, Evidence 없는 수치 금지. 각 모듈 변경에는 단위 테스트를 작성하고 통합 테스트 실패 시 다음 기능으로 넘어가지 않는다. PRD의 제안은 이 지침을 무효화하지 않는다.
- 기존 2.0은 Streamlit, SQLite/SQLAlchemy, Repository, Collector, Evidence/Fact, Analytics, Narrative 및 Report 기반을 갖고 있다. PRD §63·§75는 FastAPI/PostgreSQL을 제안하지만, PRD §77은 먼저 기존 구조와 관례를 조사하도록 한다. 이전 [설계 초안](docs/superpowers/specs/2026-10-23-issuescope-engine-design.md)은 FastAPI/PostgreSQL 도입을 배제하고 기존 UI/DB 재사용을 제안해 PRD와 충돌한다. 이 초안과 [구현 계획](docs/superpowers/plans/2026-10-23-issuescope-engine.md)은 구현 승인이나 최신 결정이 아니며, 구현 전 PRD 및 사용자 지침 기준으로 재검토·수정해야 한다.
- 기존 2.0의 `Issue`는 근거 기반 분석 그룹이다. 사용자 입력 Research Issue와 같은 개념이라고 간주하지 않는다. PRD 구현 시 기존 모델명과 저장/워크플로 경계를 확인하고, 구체 schema 변경은 사용자 지침을 만족하는 설계가 확정된 뒤에만 진행한다.
- 결정(2026-11-17, 사용자) — 기준 문서는 [V1 구현 계획서](docs/superpowers/plans/2026-11-17-aiporg-v1-implementation.md): V1은 SQLite+Stage Cache, Postgres/pgvector·워크플로 엔진은 향후 확장(시점은 안정화 후 확정). LLM은 로컬 Qwen 기본 + OpenAI·Gemini 활용 유지. 2.0 자산(Streamlit·Narrative 승인·HWPX) 유지. 다수 이슈 월간 종합은 V1 포함(Phase 4). 추가 확정: 반복 조사 루프 V1 제외, Fact Review 최소 기능 V1 포함, 워크플로 엔진 보류, Postgres는 V1 이후. AGENTS.md 1~9 유효, 새 schema는 설계 승인 후. 현재 순서: 세 이슈 검토 화면으로 Phase 2 종료 → Phase 3(키워드·정량).
- Fact Review 최소 기능(2026-11-17): `ReviewSession.fact_selected`("kf0"/"tl0" 위치 키, 기본 유지·해제 시 제외, 기존 세션은 전부 유지)와 `set_fact`/`reviewed_fact()`를 추가했다. 검토 화면 맨 위 '0. 핵심 사실'에서 사실·일정을 출처 링크와 함께 해제할 수 있고 분석 시 `reviewed_fact()`가 보고서에 쓰인다. 요약·현재 상태는 편집 불가(그대로 사용). 단위 테스트 추가, 연관 테스트 166 passed, 전체 `tests_v2`+`tests` 472 passed(2026-11-18). 다음: 사용자가 세 이슈를 검토 화면으로 검토 → Phase 2 종료 → Phase 3.
- Phase 3 키워드 분석 V1(2026-11-21): `app/search/opinion.py::refine_keywords`가 기존 `top_keywords`(문서 빈도) 후보 40개에 대해 Qwen에게 drop/merge/phrases만 짧게 답하게 하고(후보 전체를 다시 쓰게 하면 8B가 느리고 거르지 못함), 코드가 전부 재검증·재집계한다: 합치기는 공통 2글자 이상 표기만, 복원 구절은 논점 이름에 글자 그대로 있고 2건 이상 글에 나올 때만, 절차어는 `GENERIC_KEYWORDS`로 제거, 더 긴 키워드 안에서만 쓰이는 짧은 단어는 흡수(허용 2건, shortcut). `KeywordCount`에 `variants`·`topic_ids` 기본값 필드를 추가(기존 JSON 호환). Qwen 실패 시 일반 빈도로 폴백(경고 로그). `top_keywords` 동률 순서가 프로세스마다 달라지던 비결정성을 이름순으로 고정. 실측(로컬 qwen3:8b, 5~12초): 석탄화력은 정의로운 전환·대체산업·지역경제 등 목표 키워드가 올라오나 에너지·국가·결실 같은 약한 단어가 남고, 삼성은 5개로 과하게 줄며(drop이 실행마다 달라짐), 폭염은 안전·체계 등 일반어가 남는다. 집계는 제목+스니펫 기준이며 본문 기준이 아니다. 전체 테스트 475 passed. 남은 일: 키워드 품질 추가 판단(검토 화면에서 키워드 제외 기능 여부), 보고서 문구에 '수집 문서 기준' 표기, 이후 채널별 언급량·추이(정량).
- Phase 3 정량 분석 V1(2026-11-21): `app/search/quant.py`의 `build_quantitative`(LLM·웹 없음)가 관련 글(`discussion_posts`)을 채널별·일별·주별(월요일 시작, KST)로 센다. 게시일 없는 글은 추이에서 제외하고 별도 집계, 기간 밖 글도 별도 집계, 게시일 확인 글이 5건 미만이면 추이 문장을 만들지 않는다. `DiscussionPost.published_at`(선택)과 `OpinionResearchResult.quantitative`(선택)·`IssueReport.volume`(기본 빈 목록)을 추가해 기존 JSON은 그대로 열린다. 보고서에 '언급량 및 추이' 섹션과 '수집 문서 기준' 한계 문구가 들어간다. 증감률·전월 비교는 비교 기간 자료가 없어 만들지 않는다. 한계: 기존 세션 3개에는 게시일이 저장돼 있지 않아(전부 미확인) 새로 수집해야 추이가 보이며, 이 환경에서는 검색 API 키가 읽히지 않아 실제 블로그·카페의 게시일 확보 비율을 확인하지 못했다(Daum은 datetime, Naver 블로그는 postdate를 사용). 이슈 간 비교와 그래프 렌더링은 미구현. 다음: 키가 있는 환경에서 한 이슈를 새로 수집해 게시일 비율 확인.
- 월간 종합 설계·계획(2026-11-21, 사용자 승인): 7월 구성 유지, 방식 B(새 엔진 수집분을 2.0에 적재해 한 코퍼스에서 모든 수치), 문서 감성은 Qwen 분류+표본 검수. 설계 [월간 종합 설계](docs/superpowers/specs/2026-11-21-monthly-synthesis-design.md), 1단계 구현 계획 [코퍼스 적재·감성 분류·검수](docs/superpowers/plans/2026-11-21-monthly-corpus-ingest-and-sentiment.md)(Task 1~9 구현 완료, 2026-11-21). 확인된 사실: 2.0 Analytics는 `metadata["sentiment"]`만 세고, `upsert_clean`은 메타데이터를 병합하지 않고 덮어쓴다(읽어서 병합 후 저장). 프로젝트 4(지표·장 조립)와 5(시각 자료·HWPX)는 1단계 결과 후 별도 계획. 알려진 공백: 코퍼스를 만드는 end-to-end 실행기가 없고, 기존 세션 3개는 게시일이 없어 전부 보류 대상이다.
- 월간 종합 1단계 구현 완료(2026-11-21): `app/research/corpus.py`(IssueCorpus), `app/collectors/replay.py`(ReplayCollector·채널 매핑·게시일 없는 글 보류), `app/workflows/ingest_issue_corpora.py`(기존 MultiQuery 수집 워크플로로 적재, 이슈명=질의, 같은 이슈명 중복은 오류), `app/sentiment/document_classifier.py`(Qwen 문서 감성 분류+근거 구절 코드 확인, `metadata["sentiment"]`에 병합 저장, 검수 완료 문서는 덮어쓰지 않음), `app/sentiment/review.py`(이슈별 표본 min(전체, 40, max(20, 20%)), 동의/수정 기록), `streamlit_app/sentiment_review.py`와 콘솔 메뉴 '4-2. 감성 분류 검수'. 전체 `tests_v2`+`tests` 511 passed(가짜 Qwen 기준). 검증 못 한 것: 실제 Qwen 분류 품질과 속도, 코퍼스를 만드는 end-to-end 실행기(저장소에 없음, `build_corpus`의 호출처 없음), 기존 세션 3개는 게시일이 없어 전부 보류됨. 같은 프로젝트에 두 번 적재하면 수집 워크플로 상태 규칙 때문에 실패한다(새 월=새 프로젝트). 다음: 한 이슈를 새로 수집해 코퍼스 생성→적재→분류 품질 실측, 그다음 프로젝트 4(지표·장 조립)·5(시각 자료·HWPX) 계획.
- 코퍼스 실행기·적재 CLI(2026-11-21): `app/research/runner.py::run_issue`(계획→사실 검색·분석·본문 수집→종합→반응 수집·후보→검토 세션과 `corpus_<name>.json` 저장, 모든 단계 성공 후에만 파일 기록, `--max-questions`로 질문 수 제한)와 CLI `python -m app.research.runner --name ... --region ... --issue ... --start ... --end ...`, 저장한 코퍼스를 기존 프로젝트에 넣는 `python -m app.workflows.ingest_issue_corpora --project-id <UUID> corpus_*.json`(프로젝트는 콘솔 1단계에서 만든 CREATED 상태). 사실 쪽 코퍼스는 질문별 분석에서 점수 2 이상·기간 내인 모든 검색 결과(8건 종합 제한과 무관). 테스트는 단계를 가짜로 바꾼 배선 검증뿐이며 실제 검색·Qwen으로는 실행하지 못했다(이 환경에 검색 API 키가 읽히지 않음). 11개 질문 전체를 로컬 Qwen으로 분석하면 이슈당 매우 오래 걸릴 수 있어 처음엔 `--max-questions 2`로 시도할 것. 다음: 키가 있는 환경에서 한 이슈 실행→게시일 확보율과 감성 분류 품질 실측.
- 첫 실측(2026-11-22, 석탄화력, `--max-questions 2`): 1·2차 실행은 로컬 Ollama의 연결 끊김/HTTP 500으로 25~35분 뒤 실패해 `QwenQueryExpansionService.chat`에 최대 3회 재시도(연결 오류·5xx만, 600초 타임아웃은 제외)를 추가했다. 3차 실행 41분 성공: 코퍼스 77건(게시일 있음 34건, 사실 쪽 WEB 43건은 전부 게시일 없음). 적재 30건(고유 29), 보류: 게시일 없음 43·채널 미매핑 4. Qwen 감성 분류 3분: 긍정 17·부정 2·중립 3·혼재 2·미분류 5. 문제: 보도자료성 기사에 '법 통과=긍정'을 붙이고 근거 구절이 사실 문장이라, 이 비율은 여론 지표로 쓸 수 없다. 분류 기준(사실 보도는 중립, 입장·평가 표현이 있을 때만 긍정/부정) 재설계와 사람 검수 필요. 프로젝트 `fb581b25-…`가 aiporg2.db에 실측용으로 남아 있다.
- 감성 프롬프트 v2(2026-11-22, `doc-sentiment-v2`): 사실 보도는 평가 표현이 없으면 neutral, `evaluative` 필드가 false인 긍정·부정·혼재는 코드가 neutral로 내림. Qwen이 인용 문장을 `reason`에 넣고 `evidence`를 비우던 문제는 필드 순서·지시로 고침. 같은 29건 재실측: 긍정 10·부정 2·중립 13·혼재 0·미분류 4(v1은 17·2·3·2·5). 남은 문제: 긍정 10건 중 일부는 여전히 사실 문장('통과했다', '밝혔다')이 근거이고, 도지사·의원 본인의 자평(이해관계자 입장)이 긍정으로 잡힌다. 이는 '도민 여론'이 아니라 '행위자 입장'이라 출처 유형(행위자 vs 일반 이용자) 구분이 필요할 수 있어 설계 결정 대기. 검수 화면 표본 검수가 필요.
- 반응 수집 조건부 확장(2026-11-23, 사용자 승인: 목표 50건, "수집 수가 적은 경우에만 확장"): `app/search/opinion.py::collect_corpus_adaptive`. 기본 중립 질의로 모은 반응 글이 50건 미만일 때만 확장한다(최대 2라운드). 1라운드(LLM 없음): 기본 질의의 2~5쪽(`DEEP_PAGES`, provider `search(..., page)`: 다음 `page`·네이버 `start`) + 기간어("2026년 8월"). 2라운드: 사실 조사의 기관·장소 + Qwen 생활어(`LifeTerms`, 코드가 편향어·이슈어·길이 검증)를 이슈명에 붙인 질의. 질의별 적합률은 기간이 아니라 관련성(이슈어 포함·구조 노이즈 아님) 기준이며 파생 질의가 원본 5건 이상에서 0.3 미만이면 그 질의의 글을 버린다. 50건에 못 미쳐도 기준을 낮추지 않고 부족한 채로 보고한다. 질의별 수확량은 `IssueCorpus.search_log`에 저장. 실측(석탄화력, 8월): 12건 → 44건(블로그 38·카페 6), 기간 밖 463건 탈락. 대부분의 증가는 기본 질의의 깊은 페이지에서 나왔고(+22), Qwen 생활어는 3건 추가에 그쳤으며 이슈와 무관한 표현이 다수였다. 한계: 검색 API에 날짜 필터가 없어 과거 월은 원본 결과의 약 10~30%만 기간 안이다. 이 확장은 새 엔진의 블로그·카페(다음/네이버)만 대상이며 2.0의 커뮤니티 5곳(dcinside·clien·fmkorea·theqoo·ruliweb)은 새 엔진 코퍼스에 연결돼 있지 않다(별도 단계). 반복 재투입 루프(채택 문서 공출현 단어 되먹임)와 은어 역추출은 하지 않았다. 전체 528 passed.
- (구) 다음 행동: 생성된 검색어를 검색 provider에 전달하고, 수집 결과를 근거 기반 Fact pipeline에 연결한다. UI 연결과 반복 조사 루프는 아직 구현하지 않았다.
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
