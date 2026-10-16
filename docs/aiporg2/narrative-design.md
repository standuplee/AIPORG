# Phase 6 Narrative 계약 불일치와 구현안

작성: 2026-09-23. 상태: **출력 저장 계약 결정·구현 완료(2026-10-16)** — 아래
"권장안"을 그대로 채택해 `app/schemas/narrative.py`(`NarrativeSentenceSchema`,
`NarrativeGenerationSchema`, `NarrativeOutputSchema`)와
`app/repositories/{narrative,sqlalchemy}.py`(`save_output`,
`get_latest_output`)로 구현했다. 상세는
`docs/superpowers/plans/2026-09-08-aiporg2-implementation.md`의 "8차"
절과 HANDOFF.md 참고. LLM adapter(Gemini, `app/narrative/llm_adapter.py`)도
같이 구현했지만, draft orchestration service와 Streamlit UI 연결은 아직
없다 — Issue/AnalyticsSnapshot이 콘솔에 연결돼 있지 않아 입력
(`NarrativeContext`) 자체를 만들 방법이 없다.

## 2026-10-16 요구 개정 (아래 과거안보다 우선)

사용자는 GPT/Claude로 월간 보고서 서술을 생성하고 Streamlit에서 직접 수정·승인한 뒤 HWPX·DOCX·Markdown으로 출력하는 흐름을 요구했다. 상세 기준은 [월간 보고서 명세](monthly-keyword-report-requirements.md)의 7~9절이다. 아래의 “이번 단계는 template만 구현”은 과거 구현 범위이며 새 목표가 아니다.

기존 두 출력 모델 권장안만으로 수정·승인 버전 및 시각 자산과의 연결이 충분한지 재검토한다. 필요한 정보는 장/이슈 단위 문장, fact/evidence/analytics 연결, 입력 스냅샷, 제공자·모델·프롬프트 버전, 초안·수정 이력, 검증 결과, 승인 대상 버전·해시, 표·그림 버전이다. 기존 DB JSON 저장 방식을 유지할 수 있는지와 repository 경로·transaction 경계부터 설계하며, 이 정보 목록을 이유로 임의 schema를 추가하지 않는다.

생성형 초안과 사용자 편집은 템플릿 문자열 완전 일치로 검증하지 않는다. 값·단위·대상·기간·분모와 근거를 검증하고 의미상 오류는 사용자 검수에서 확인한다. 기존 결정론적 renderer와 엄격한 검증은 fallback 경로에 유지한다.

초안 저장과 사용자 승인은 별개다. 승인본은 본문·집계·표/그림·템플릿 버전을 함께 고정한다. 데이터나 본문 수정 시 새 버전의 승인이 필요하며 이전 승인본과 파일은 보존한다. 기존 NARRATIVE_COMPLETED 상태를 최종 사용자 승인으로 간주하지 않는다. 기존 workflow 상태와 검수 상태의 연결은 계약 결정 대상이다.

Writer는 승인본만 읽고 재서술·새 사실 생성·LLM 호출을 하지 않는다. HWPX·DOCX·Markdown에 동일한 승인 콘텐츠를 전달한다. 새 schema 및 persistence 구현은 아직 하지 않았다.

## 확인된 불일치

현재 `NarrativeContext`는 issue, facts, sentiment, keywords,
positive_reasons, negative_reasons만 허용한다. `NarrativeRead`도 이 입력 모델의
alias다. `NarrativeRepository.save/get_latest`는 입력 context만 저장·반환한다.
문장, 문장별 source mapping, analytics 참조 또는 실행 version을 표현하는
출력 contract는 없다. 기존 contract test는 필드 집합을 고정한다.

Phase 6의 완료 조건인 '서술 문장과 근거 매핑 저장'은 현재 계약만으로 표현할 수
없다. positive_reasons/negative_reasons에 통계나 출력 문장을 넣으면 필드 의미가
바뀌므로 사용하지 않는다. 기존 model 이름과 필드, 기존 save/get_latest는 유지한다.

AGENTS.md의 '임의 schema 추가 금지'와 구현 계획의 '기존 schema로 불가능하면
설계 문서에 불일치를 기록하고 별도 결정을 받는다'에 따라 아래 출력 계약만
명시적으로 결정한 뒤 persistence와 workflow를 연결한다.

## 권장안: 명시적인 출력 모델, 기존 DB JSON 활용

새 Pydantic 출력 모델 2개만 추가한다. 기존 모델은 변경하지 않는다.

- `NarrativeSentenceSchema`: `text`, `fact_ids`, `evidence_ids`, `document_ids`,
  `analytics_paths`. 각 문장은 Fact 또는 analytics 경로를 반드시 가진다.
- `NarrativeOutputSchema`: `project_id`, 기존 `VersionedRunSchema`의 `run`,
  `analytics_run_id`, `sentences`.

기존 `narratives.context` JSON에 구분 가능한 envelope로 출력 payload를 저장한다.
기존 입력 context 행은 그대로 읽을 수 있어야 한다. DB 컬럼이나 테이블은 추가하지
않는다. repository에 `save_output`, `get_latest_output`을 추가하고, 기존
`get_latest`는 입력 context 행만 조회하게 한다. 출력 전체는 프로젝트 단위이고
기존 nullable issue_id는 null로 저장한다.

`AnalyticsToNarrativeWorkflow`는 ANALYTICS_COMPLETED에서만 시작한다. 저장된
최신 analytics, 연결 issue/fact, evidence를 읽고 VERIFIED/SUPPORTED Fact만
허용한다. Fact claim은 evidence 문구와 대조한다. 불확실한 Fact와 근거 없는
감성 이유를 서술하지 않는다. 분석 수치는 snapshot 값을 그대로 표현한다.
새 문장은 결정론적 템플릿으로 생성하며 생성 후 동일 근거·템플릿과 대조한다.
숫자나 고유명사뿐 아니라 승인되지 않은 문장 변경 자체를 거부한다.

출력 저장과 NARRATIVE_COMPLETED 전환은 같은 transaction에 둔다. 실패 시
롤백한다. 빈 입력은 빈 문장 목록을 저장하며 '근거 없음'을 사실 문장으로
추정하지 않는다. LLM adapter는 선택 사항이므로 이번 단계는 template만 구현한다.

## 대안

새 모델 없이 위 payload를 기존 JSON에 저장할 수 있으나, 이것도 새로운 JSON
출력 계약이며 명시적 결정이 필요하다. 런타임 검증과 반환 타입이 약해지므로
권장하지 않는다.

## 결정과 무관하게 가능한 작업

- 기존 전체 테스트 게이트 검증
- 기존 NarrativeContext와 AnalyticsSnapshot을 입력으로 받는 순수 템플릿 renderer
- 허용된 Fact만 사용하고 입력에 없는 문장을 거부하는 사후 검증 및 unit test

출력 계약 결정 전에는 신규 schema, JSON 저장 형태, DB write 경로를 추가하지 않는다.

## 2026-09-23 검증 결과

- `TemplateNarrativeService` 구현: 기존 입력 contract로 지원된 Fact 문장 인용과
  analytics 문서 수를 표현하고, 출력이 허용된 템플릿과 정확히 같은지 사후 검증함.
- 문서 수의 정수·음수·근거 ID 중복/건수 정합성을 확인함.
- VERIFIED/SUPPORTED만 사용하며 프로젝트·문서 ID·Evidence의 완전한 문장이
  일치해야 함. 부분 문자열로 다른 숫자나 고유명사를 뒷받침하는 경우를 차단함.
- 추가 unit test 20개, 기존 전체 테스트를 포함하여 `254 passed`.
- `git diff --check` 통과. 새 narrative 모듈에 웹·LLM·DB 접근 없음.
- 이 결과는 순수 템플릿과 기존 기능 회귀 검증임. 신규 출력 schema, 문장별
  source mapping 저장, Narrative workflow 통합은 계약 결정 전이므로 미구현이며
  Phase 6 전체 완료 또는 NARRATIVE_COMPLETED 도달을 의미하지 않음.
