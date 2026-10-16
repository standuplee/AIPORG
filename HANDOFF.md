# AIPORG 공통 작업 인계

Codex와 Claude Code가 같은 저장소 작업을 이어받기 위한 현재 상태 문서다. 작업 시작 시 실제 파일과 `git status`를 확인하고, 사용자의 최신 요청을 우선한다.

## 제품 목표와 사용자 결정 (2026-10-16)

**추가 확정 요구:** 표·그림·차트·인포그래픽도 생성 이후 UI에서 개별 확인·수정·승인해야 한다. 상세 명세 8.1절 및 AT-17~21에 편집 항목, 원자료 수정과 연관 본문 갱신, 재렌더링·버전 비교·개별 승인·최종 승인 게이트를 추가했다. 편집 데이터/설정과 렌더 결과를 함께 저장한다. 승인 후 변경한 자료는 재승인이 필요하며, 포함된 모든 자료의 현재 버전이 승인되어야 최종 보고서를 승인·출력한다. 초기 UI는 폼·표·설정 패널과 미리보기 방식이며 자유 캔버스 편집은 별도 확장이다. 이번 추가 작업도 문서만 수정했으며 UI 구현 완료가 아니다.

**최신 상세 기준:** [월간 키워드 보고서 요구사항](docs/aiporg2/monthly-keyword-report-requirements.md). 사용자 제공 7월 PDF 12쪽을 텍스트와 전체 페이지 이미지로 확인하고 페이지별 제작 명세, 수집·산식, 표/인포그래픽, Streamlit, LLM, HWPX, 구현 순서, 인수 조건 AT-01~16을 기록했다. 3월 PDF보다 7월 기준본을 우선한다. 매월 키워드 4~5개가 바뀌며 실제 수집 결과에 따라 서술·표·그림·출처를 모두 새로 만든다. 4개 이슈는 12쪽 기본 목표, 5개 이슈·장문은 페이지 확장. 일반 표·본문은 편집 가능해야 한다.

기준본의 추정 수치·별점·외부 조사·Lucy 사용 문구는 실제 데이터나 시스템 기능으로 복사하지 않는다. 검색 경로(네이버/다음/구글)와 원문 채널을 구분하고 같은 기사를 중복 집계하지 않는다. 온라인 감성과 별도 표본조사를 구분한다. **기본 조사어는 사용하지 않고 월별 키워드 리스트만 쓰며, 댓글은 포함한다(2026-10-16 확정, 아래 "확정된 결정" 참고).** 커뮤니티 목록·플랫폼 접근 권한·원본 HWPX/자산은 아직 확인 대상이다.

온라인 여론을 수집·정제하고 근거가 연결된 사실과 수치를 집계한 뒤, **GPT 또는 Claude를 연결한 생성형 LLM이 보고서 서술 초안을 작성**한다. 사용자가 UI에서 초안을 직접 검수·수정·승인한 다음에만 **Word(DOCX)·Markdown·HWPX**를 생성한다. 예전처럼 외부 챗에 분석 내용을 복사해 다시 쓰고 Word에 수동으로 옮기는 과정을 없애는 것이 목적이다.

권장 흐름: `수집 → 정제·중복 제거 → Evidence/Fact/Issue → AnalyticsSnapshot → LLM 서술 초안 → 근거·수치 자동 검증 → 사용자 UI 검수·수정·승인 → 승인된 동일 본문에서 DOCX/Markdown/HWPX 출력`. LLM 호출은 Narrative 계층에 둔다. Collector의 LLM 호출 금지, Analyzer의 웹 요청 금지, Writer의 새 사실 생성 금지 규칙은 유지한다. LLM 결과와 사용자 수정본 모두 숫자·사실·출처 연결을 검증하고, 근거 없는 문장은 승인 전에 표시하거나 차단하도록 설계한다. 형식별 writer가 LLM을 다시 호출하거나 각자 내용을 재작성하지 않는다.

검수 UI에는 원문·근거 링크와 집계값을 서술 문장 옆에서 볼 수 있는 화면, 문장 수정과 재생성, 저장된 초안의 버전 비교, 승인 후 출력 형식 선택이 필요하다. 승인 전 자동 보고서 발행은 하지 않는다. **첫 검수 UI는 Streamlit이 유력하다**(2026-10-16 사용자 제안에 대한 권장안). 편집 중 화면 상태와 별개로 초안·수정 이력·승인 기록은 repository를 통해 DB에 저장한다. 여러 검수자의 권한 관리나 복잡한 편집 화면이 필요해지면 UI 구성을 다시 평가한다. GPT/Claude 연결은 각 제공자의 API 인증·비용을 별도로 검토해야 하며, CLI 구독 세션을 그대로 백엔드 API로 취급하지 않는다.

## HWPX 구현 방향

`airmang/python-hwpx`를 AIPORG와 별도 저장소로 clone/fork하여 의존성으로 사용한다. 로컬 개발에서는 editable 설치를 쓸 수 있지만, 재현 가능한 배포·CI에는 fork의 고정 커밋이나 릴리스를 지정한다. **아직 clone, fork, 설치, 코드 연결은 하지 않았다.**

AIPORG 전용 보고서 목차·표지·서식·차트 PNG 배치와 형식별 출력은 AIPORG의 Report/Writer 계층에 둔다. HWPX 포맷 자체의 부족한 기능·버그는 별도 `python-hwpx` fork에서 추가한다. HWPX 첫 시제품은 기존 보고서 데이터로 표지·요약·표·차트·출처를 만들고 실제 한컴에서 열림, 페이지 배치, 줄바꿈, 표 넘침을 확인한다.

## 현재 구현 상태와 제약

- AIPORG 2.0 진행 기록: `docs/superpowers/plans/2026-09-08-aiporg2-implementation.md`. 마지막 "진행 기록"(8절, 날짜 기준)은 Phase 5 완료(2026-09-21)지만, **그 뒤에 추가된 "2026-10-16" 절들(코드 검증 기반 상세 구현 계획 → 사용자 결정 반영 3차 → Streamlit 콘솔 MVP와 테스트 환경 확인 4차)이 실제 현재 상태다.** Phase 완료 기록만 보고 기능이 끝났다고 판단하지 말 것 — 아래가 코드 대조 결과다.
- 코드 확인 결과(2026-10-16): `app/`에 `hwpx`/`openai`/`anthropic`/`gpt`/`llm` 실제 코드가 없다(HWPX·LLM 연동 0%). `app/collectors/naver_news.py`는 `start=1, display=100` 고정 단일 요청만 하고, `app/collectors/daum_news.py`는 `meta.is_end`까지 이미 페이지 순회한다(월경계 조기 종료 조건만 없음). `app/models|schemas/{report,visualization}.py`는 각 20~40줄의 빈 contract뿐이고 렌더링/차트/문서 writer가 없다. 1.0(`aiporg/`)에는 2.0으로 아직 포팅 안 된 차트(`aiporg/charts/*`), DOCX writer(`aiporg/report/docx_writer.py`), 블로그/커뮤니티(`aiporg/collect/*`), 유튜브(`aiporg/youtube/*`) 코드가 있다.
- **Streamlit 콘솔이 이제 실제로 존재하고 동작한다.** `streamlit_app/console.py` — 아래 "Streamlit 실행 방법" 참고. 8화면 중 1(프로젝트)·2(수집 실행)·3(수집 결과·진행상황)은 실제 repository/service를 호출하는 동작 코드이고, 4(통계)는 아직 연결 안 됐다는 안내만, 5~8(서술/시각자료/보고서 미리보기/출력)은 왜 아직 안 되는지 명시한 "미구현" 패널이다. `streamlit.testing.v1.AppTest`로 8화면 전환과 프로젝트 생성이 예외 없이 동작하고 SQLite에 실제 행이 쓰이는 것까지 확인했다(실 네이버/다음 API 키로의 네트워크 호출은 하지 않음).
- Phase 6의 순수 템플릿 서술·검증은 일부 구현됐다(`app/narrative/template.py`, 입력 전용 `NarrativeContext`). 출력 계약 결정, 저장, 문장별 근거 매핑, LLM 초안, 사용자 승인, Narrative workflow 통합은 아직 구현되지 않았다.
- 새 schema나 workflow 상태를 임의로 추가하지 않는다. LLM 초안·수정본·승인본, 시각 자료(Visualization), Report bundle의 저장 계약과 승인 게이트를 먼저 설계 문서에 명시하고 결정한 뒤 구현한다(구현 계획 §2). Streamlit 콘솔 작업 중에는 **core(`app/`) 계약을 하나도 바꾸지 않고** 기존 repository/service만 조합해서 화면 1~3을 만들었다 — 신규 schema 없이 가능한 범위였음이 실제로 확인됨.
- 작업 트리에는 이 인계 설정 이전부터 다수의 미커밋 변경이 있다. 인계받는 도구는 이를 기존 작업으로 보존한다.
- **테스트 환경: 확인·해결됨(2026-10-16, 4차).** 시스템 `/usr/bin/python3`(3.9.6)에는 `matplotlib==3.11.0`이 설치되지 않는다(3.10+ 필요). 저장소 루트에 Homebrew Python 3.12로 `.venv`를 만들어 `requirements-dev.txt`(+ `streamlit`)를 설치했고, `tests_v2`+`tests` **254 passed**를 실제로 확인했다(narrative-design.md의 2026-09-23 기록과 일치). `.venv/`와 `aiporg2.db`는 `.gitignore`에 추가함.
- `AGENTS.md`의 기존 1~9번 개발 규칙을 유지한다. 같은 checkout에서는 한 번에 한 도구만 파일을 수정한다. 별도 worktree를 쓰면 인계 파일과 코드 변경을 함께 전달한다.

## Streamlit 실행 방법

```bash
# 최초 1회
/opt/homebrew/bin/python3.12 -m venv .venv   # 시스템 python3(3.9.6)는 matplotlib 핀 버전과 호환 안 됨
.venv/bin/pip install -r requirements-dev.txt

# 실행 (매번)
.venv/bin/streamlit run streamlit_app/console.py
```

최초 실행 시 Alembic migration을 자동 적용해 `aiporg2.db`를 만든다. 네이버/다음
수집을 실제로 돌리려면 `.env` 또는 쉘 환경변수에 `AIPORG2_NAVER_CLIENT_ID`,
`AIPORG2_NAVER_CLIENT_SECRET`, `AIPORG2_KAKAO_REST_API_KEY`를 설정한다 — 없으면
해당 채널 체크박스가 비활성화되고 "자격증명 없음"이라고 표시된다(앱이 깨지지
않는다). 파일명을 `app.py`로 바꾸지 말 것 — 저장소 루트의 `app/` 패키지와 이름이
충돌해 import가 깨진다(이번에 실제로 재현하고 `console.py`로 고쳤다).

알려진 한계: 프로젝트 목록·프로젝트의 전체 run 목록을 조회하는 repository
메서드가 없어서, 지금은 같은 브라우저 세션 동안 만든 프로젝트/실행한 수집만
화면에 남는다(앱 재시작 시 사라짐, 기존 프로젝트는 UUID로 다시 불러와야 함).
수집 실행은 `CollectionService`만 쓰고 정제→Evidence(`CollectionToEvidenceWorkflow`)
는 아직 연결 안 했다(그 workflow는 project당 한 run만 받는 구조라 키워드 N개
fan-out과 바로 안 맞음 — M1에서 설계 필요).

## 구현 계획 한눈에 보기

아래 상태는 기존 구현 기록과 사용자 요구를 합친 것이다. `docs/superpowers/plans/2026-09-08-aiporg2-implementation.md` 상단에 2026-10-16 개정 절들을 추가했다. 과거 계획과 충돌할 때 개정 절 및 상세 월간 보고서 명세가 우선한다.

| 단계 | 구현 내용 | 상태 |
| --- | --- | --- |
| Phase 0~2 | 1.0과 분리한 `app/` 계약·상태 머신, 테스트 환경, DB migration·repository 구현 | 완료, 2026-10-16 재확인(254 passed) |
| Phase 3 | 수집 → 정제·중복 제거 → Evidence 저장과 실패 후 재개 | 기록상 완료(네이버/다음 중심, 월간 전체 수집 아님) |
| Phase 4 | Evidence → 검증된 Fact → Issue 확정과 출처 역추적 | 기록상 완료 |
| Phase 5 | canonical 문서 기준 언급량·채널·키워드·감성·비교기간 집계와 AnalyticsSnapshot | 기록상 완료 |
| Phase 6 | GPT/Claude 서술 초안, 근거·수치 검증, 초안·수정·승인 버전 저장, Streamlit 검수 UI | 템플릿 서술 일부 + Streamlit 콘솔 화면 1~3 동작; 나머지 미구현 |
| Phase 7 | 승인본과 AnalyticsSnapshot에서 차트·보고서 조립, DOCX·Markdown·HWPX 출력 및 실제 HWPX 열림·배치 검증 | 미구현 |
| Phase 8 | 프로젝트 실행·상태·재시도·승인본·산출물 조회를 위한 API/CLI와 운영 설정 | 미구현 |

개정 실행 순서는 **M0 계약·템플릿 기준 → M1 실제 다중 채널 수집 보완 → M2 분석·근거 보완 → M3 LLM 초안 → M4 Streamlit 검수·승인 → M5 표·그림 및 HWPX → M6 동일 승인본 3형식 출력·운영**이다. 각 모듈 unit test, 단계별 integration test, 기존 1.0 회귀 테스트를 통과한 뒤 진행한다. 승인되지 않은 초안은 최종 보고서로 내보내지 않는다.

## 정확한 다음 행동

1. `ProjectRepository`/`CollectionRunRepository`에 "프로젝트 목록"·"프로젝트의 전체 run 목록" 조회 메서드를 추가한다(신규 schema 아닌 조회 메서드). Streamlit 콘솔이 세션 재시작 후에도 기존 프로젝트/실행 이력을 보여주려면 필요하다.
2. 키워드 N개 fan-out을 `CollectionToEvidenceWorkflow`(정제→중복제거→Evidence)까지 연결하는 orchestration을 설계한다 — 현재 그 workflow는 project당 한 run만 받는 구조라 그대로 못 쓴다.
3. Narrative 출력·Visualization·Report의 초안·수정·승인·문장 근거·시각 자산 버전 저장 계약을 명시적으로 결정한다(구현 계획 §2, §7 결정 목록 중 미해결: HWPX 자산 확보, Narrative/Visualization/Report 계약, LLM provider 최종 선택/비용, 1.0 수집기 포팅 범위).
4. 네이버 collector에 페이지 순회를 추가하고(다음은 이미 있음), 구글 수집기를 신규로 만든다(1.0에도 코드 없음 — 2026-10-16 결정으로 범위 포함됨). 커뮤니티(클리앙/디시/펨코/루리웹/더쿠)·블로그·유튜브는 1.0 코드를 2.0 계약으로 포팅한다.
5. mock LLM adapter(키 없이 template fallback) → 시각 자료 2종(채널 도넛, TOP10 카드)만 편집 UI에 연결 → HWPX 3쪽(표지/목차/요약) 시제품 순으로 1차 최소 단위를 넓힌다(구현 계획 §6).
6. 별도 python-hwpx를 연결하고 7월 보고서의 대표 페이지 시제품을 실제 한컴에서 검증한다.

## 확정된 결정 (2026-10-16)

- **고정 조사어 미사용.** 지역·기관·인물 기본 조사어를 검색어에 자동 추가하지
  않는다. 사용자가 매월 Streamlit에 입력하는 키워드 리스트(개수 가변, 4~5개
  고정 아님)가 그 달 조사 범위 전부다. `TargetSchema`는 맥락 정보로만 쓰고
  검색어에 병합하지 않는다. 키워드 리스트는 이미 있는
  `QuerySetRepository.create(project_id, queries)`로 저장한다(Project에 별도
  필드를 신설하지 않음 — 정정: 이전 절에서 "CollectionRun.query로 암묵 표현"이라고
  썼던 것은 이 repository를 놓친 부정확한 서술이었음).
  예(2026년 9월, 실행 예시로만 기록): 공공기관 충남 2차 이전·내포신도시 / 충남
  재정전략회의 / 인사청문특위 부적격판단 전격수용 / 삼성 디스플레이 67조 투자유치.
- **댓글 포함.** 신규 필드 대신 기존 `RawDocument.metadata`에
  `document_type`("article"/"comment")·`parent_document_id` 컨벤션으로 저장(감성
  라벨을 `metadata["sentiment"]`에 저장한 기존 선례와 동일 패턴, 신규 schema
  아님). analytics 집계는 article/comment를 분리한다. (아직 collector에 실제
  구현 안 됨 — M1 대상.)
- **LLM은 API 직접 연결, 키는 추후 제공.** CLI 구독이 아니라 API 호출로 확정.
  키가 없을 때 adapter는 기존 template 서비스로 자동 fallback해야 한다. GPT/Claude
  중 어느 쪽을 쓸지는 미정 — provider를 설정값으로 선택 가능하게 구현.
- **X·인스타그램 제외, 구글 포함.** X·인스타그램은 유료 접근으로 판단해 1차
  범위에서 완전히 뺀다. 구글은 범위에 포함하되 수집기는 아직 미구현.
- **커뮤니티 목록은 1.0 그대로.** clien/dcinside/fmkorea/ruliweb/theqoo 5개
  사이트를 그대로 쓴다. 2.0 포팅(수집기 작성)은 아직 안 함.
- **Streamlit 배치: `streamlit_app/console.py`, 로컬 전용.** 위 "Streamlit 실행
  방법" 참고.
- **테스트 가상환경: Homebrew Python 3.12 + `.venv/`.** 위 "현재 구현 상태와
  제약" 참고.

## 사용자가 결정할 사항 (미해결, 상세는 구현 계획 §7)

1. 원본 HWPX/로고/표지 사진 확보 가능 여부
2. Narrative 출력·승인·시각 자산 버전 계약 제안안 채택 여부
3. LLM provider(GPT/Claude) 최종 선택, API 키/비용 책임, 월 예산
4. 1.0 유튜브/커뮤니티/블로그 수집기 "포팅" vs "재작성" 여부와 범위

## 이번 문서 작업과 검증 (2026-10-16, 4차)

- 사용자가 X·인스타그램 제외/구글 포함, 커뮤니티 목록 현행 유지를 확정하고
  "Streamlit을 실행할 수 있는 명령어"와 "프로젝트 자체가 Streamlit 기반으로
  실행되도록" 요청했다. 이전 3번의 세션과 달리 **이번에는 실제 코드를 작성하고
  실행까지 검증했다.**
- 신규 코드: `streamlit_app/console.py`(화면 1~3 동작, 4~8 명시적 미구현 패널).
  core(`app/`) 계약은 변경하지 않았다 — 기존 `ProjectRepository`,
  `QuerySetRepository`, `CollectionService`, `CollectionRunRepository`,
  `DocumentRepository.list_raw_by_collection_run`만 조합해서 만들었다.
- `.venv`(Python 3.12) 구성, `requirements-dev.txt`에 `streamlit` 추가,
  `tests_v2`+`tests` 254 passed 확인, `.gitignore`에 `aiporg2.db` 추가.
- `streamlit.testing.v1.AppTest`로 8화면 전환 전부와 프로젝트 생성 폼 제출을
  실행해 예외 없음과 실제 SQLite 행 생성을 확인했다. 가짜 collector로
  `CollectionService` → `CollectionRunRepository.get` →
  `DocumentRepository.list_raw_by_collection_run` 경로도 실행해 확인했다. 실제
  네이버/다음 API 네트워크 호출은 하지 않았다(키 미설정).
- 과정에서 발견·수정한 버그: (1) 파일명을 `app.py`로 했을 때 `app/` 패키지와
  이름 충돌로 import가 깨짐 → `console.py`로 변경. (2) "출력·이력" 페이지의
  미구현 안내 딕셔너리 key가 사이드바 라벨과 달라 `KeyError` → key를 맞춤.
- 이전 세션 서술 오류 2건을 코드 재확인으로 정정했다(구현 계획 문서에도 반영):
  daum_news.py는 실제로는 페이지 순회를 이미 하고 있었고(naver만 단일 요청),
  키워드 리스트 저장은 `QuerySetRepository`가 이미 있어 "신규 저장 계약 필요"가
  아니라 "이미 있는 repository를 쓰면 됨"이었다.
- 기존 미커밋 변경은 보존했고, `app/` 하위 core 코드는 건드리지 않았다.

작업을 이어받는 도구는 완료 작업·변경 파일·검증 결과·막힌 점·다음 행동을 이 문서에 최신 상태로 갱신한다. 채팅 원문이나 비밀값은 기록하지 않는다.


## 기능 완료 시 커밋·푸시 규칙
- 기능 단위의 구현과 필요한 테스트가 완료되면 `HANDOFF.md`를 최신 상태로 갱신한 뒤 해당 기능의 변경만 선별하여 커밋하고 원격 브랜치에 푸시한다.
- 커밋 전 `git status`와 diff를 확인한다. 다른 작업자의 변경, 무관한 파일, 비밀값은 포함하지 않는다. 테스트가 실패하거나 기능이 미완성이면 완료 커밋으로 처리하지 않고 상태를 `HANDOFF.md`에 기록한다.
- 커밋 메시지는 `<type>(scope): <subject>` 형식을 사용한다. `scope`는 변경 영역을 나타내며 필요 없으면 생략할 수 있다. 제목은 변경 내용을 짧고 구체적으로 설명한다.
- 타입은 `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore` 중 변경 성격에 맞게 선택한다. 설명이 필요한 경우에만 본문을 쓰고, 관련 이슈가 있을 때만 푸터를 쓴다.
- 커밋 메시지에 `commit by Claude`, `Co-authored-by`, 도구 이름, 자동 생성 문구를 넣지 않는다. 변경 내용에 필요한 메시지만 작성한다.
- 푸시가 실패하면 강제 푸시하지 않는다. 실패 원인과 커밋 상태를 `HANDOFF.md`에 기록하고 충돌을 확인한다.