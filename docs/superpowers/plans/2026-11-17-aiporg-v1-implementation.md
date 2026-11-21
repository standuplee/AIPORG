# AIPORG 온라인 여론 분석 및 보고서 자동화 시스템 — 구현 계획서 (Revised V1)

> 기준 문서. 2026-10-23의 `issuescope-engine` 설계 초안·구현 계획은 이 문서로 대체되었다. 제품 요구사항 원문은 루트 `PRD.md`, 작업 상태는 루트 `HANDOFF.md`.

## 0. 확정된 결정 (2026-11-17, 사용자)

1. **DB:** V1은 SQLite + JSON 세션/Stage Cache. PostgreSQL/pgvector는 향후 확장이며 전환 시점은 V1 안정화 이후 확정한다. 워크플로 엔진도 그때 함께 검토한다(V1에서는 도입하지 않음).
2. **LLM:** 로컬 Qwen(Ollama)을 기본으로 하고 OpenAI·Gemini 어댑터도 활용 대상으로 유지한다. 사실 생성 금지 등 AGENTS.md 규칙은 모든 모델에 동일 적용한다.
3. **기존 2.0 자산 유지:** Streamlit 콘솔, 수집→Evidence→Fact, Narrative 승인 흐름, HWPX 시제품을 유지한다. 내보내기 형식에 HWPX를 포함한다.
4. **다수 이슈 월간 종합은 V1 범위**다(§11에서 승격, Phase 4).
5. **스키마 규칙:** 기존 `Issue`·`Report` 등 모델명은 변경하지 않으며, 새 모델은 이름을 구분하고 설계 승인 후에만 추가한다(AGENTS.md 1·2번).

6. **정보 공백 기반 반복 조사 루프: V1 제외.** 조사 범위 확대, 실행시간·비용·결과 변동성 증가를 피한다. (`missing_information`은 보고서에 표시만 한다.)
7. **Fact Review 화면: V1에 최소 기능 포함.** 사실 오류가 최종 보고서에 그대로 반영되는 것을 막는다(핵심 사실·수치·일정·출처의 승인/제외).
8. **워크플로 엔진: 도입 보류.** 현재 규모는 Python 단계별 실행과 상태 관리(Stage Cache)로 충분하다.
9. **PostgreSQL 전환: V1 이후.** SQLite로 단일 사용자·로컬 분석 업무를 처리할 수 있다.

미결정 사항 없음(Postgres 전환 시점만 V1 안정화 후 재검토).

## 1. 프로젝트 개요

**프로젝트명:** AIPORG (AI-powered Public Opinion Research & Generation)
**도메인:** 공공정책·지역 현안·온라인 여론 분석
**목적:** 지방자치단체의 주요 정책·지역 현안에 대한 자료 조사, 온라인 여론 분석, 월간 보고서 작성 업무 자동화

**기술 스택**

- Backend: Python 3.12, FastAPI, Pydantic
- Database: SQLite (Postgres/pgvector는 향후)
- Data Processing: Pandas
- LLM: Qwen(Ollama, 기본), OpenAI API, Gemini API
- Data Collection: Naver Search API, Daum/Kakao Search API
- Web Extraction: Requests, Trafilatura, BeautifulSoup
- Frontend: Streamlit (MVP)
- Export: Markdown, HTML, DOCX, HWPX

## 2. 프로젝트 목표

기존 월간 여론 보고서는 담당자가 현안을 선정한 뒤 관련 뉴스·게시글을 직접 검색해 핵심 사실, 주요 논점, 여론 반응을 정리했다. AIPORG는 반복되는 검색·수집·정리·분석·작성 업무를 자동화한다.

1. 사용자가 지정한 이슈의 자료를 자동 검색·수집한다.
2. 주요 사건과 정책 현황을 사실 중심으로 정리한다.
3. 온라인 논점과 실제 반응을 구분해 분석한다.
4. 채널별 언급량, 주요 키워드, 여론 특성을 분석한다.
5. 분석 결과와 출처로 월간 보고서를 자동 생성한다(다수 이슈 종합 포함).
6. 담당자가 결과를 검토하고 최종 확정한다.

**범위:** 사용자가 이슈를 선정한다. 자동 이슈 발굴, 자율 연구 주제 선정, 복잡한 팩트체킹은 제외한다. 검색 결과를 전체 여론의 대표 표본으로 간주하지 않는다.

## 3. 전체 시스템 아키텍처

```text
[User Input] 지역 / 분석 기간 / 이슈
  ▼
[1. Query Expansion]  Qwen 기반 조사 항목·검색 질의 생성
  ▼
[2. Multi-Source Collection]  Naver News/Web/Blog, Daum Web/Blog/Cafe
  ▼
[3. Data Processing]  URL·제목 중복 제거, 기간·관련도 필터, 본문 추출·정규화
  ├───────────────┐
  ▼               ▼
[4. Fact Research]  [5. Online Research]
 핵심 사실·현황·일정·출처   논점 Discussion / 반응 Reaction / 키워드 / 채널 특징
  └───────┬───────┘
          ▼
[6. Quantitative Analysis]  채널별 언급량, 시계열, 키워드 빈도
          ▼
[7. Human Review]  사실·논점 검토, 반응 사용/제외
          ▼
[8. Report Generation]  근거 기반 문장 생성, 표·그래프, 이슈별 → 월간 종합
          ▼
[9. Export]  Markdown / HTML / DOCX / HWPX
```

## 4. 상세 기능 설계

### 4.1 Issue Input & Query Expansion

사용자가 입력한 이슈를 검색 가능한 조사 질문과 질의로 확장한다.

```json
{"region": "충청남도", "start_date": "2026-08-01", "end_date": "2026-08-31", "issue": "석탄화력폐지지역 특별법"}
```

처리: 핵심 요소(지역·기관·정책·사업·날짜) 식별 → Qwen 조사 질문 생성 → 질문별 검색 질의 생성 → 중복 제거·검증 → 검색 목적별 분리.

| 유형 | 목적 |
|---|---|
| FACT_RESEARCH | 사건 발생 여부, 정책 현황, 주요 일정 |
| OPINION_CORPUS | 이슈 관련 온라인 게시글 수집 |
| FRAME_DISCOVERY | 주요 쟁점·평가 관점 탐색 |

여론 수집용 검색어는 중립적으로 생성한다. `기대`·`우려`·`논란` 등 반응 유도 표현은 일반 여론 표본 수집에 쓰지 않는다. 출력: SearchPlan JSON. **구현 상태: 완료**

### 4.2 Multi-Source Data Collection

| Provider | Channel | 용도 |
|---|---|---|
| Naver | News | 사건·정책 기사 |
| Naver | Web | 공식 자료·일반 웹 문서 |
| Naver | Blog | 개인·기관 게시글 |
| Daum/Kakao | Web | 일반 웹 문서 |
| Daum/Kakao | Blog | 블로그 게시글 |
| Daum/Kakao | Cafe | 커뮤니티 게시글 |

채널별 API 연동, 통합 SearchResult, URL 정규화, URL·제목 중복 제거, 한 Provider 실패 시 나머지 유지, 수집 시점·게시일 관리. 출력: SearchResult[]. **구현 상태: 완료** (검색 단계 기간 필터는 미구현)

### 4.3 Data Filtering & Article Fetcher

처리: 기간 확인 → 이슈·조사 질문 관련도 평가 → 중복 제거 → 주요 문서 선별 → 본문 추출 → HTML 노이즈 제거·정규화. Qwen은 질문과 결과의 의미적 관련성만 판단하고(읽을 문서 선별 용도, 사실 판단 아님), 코드는 URL 정규화·게시일/기간 판정·출처 유형·중복·ID 관리를 담당한다. 출력: FetchedDocument[]. **구현 상태: 완료**

### 4.4 Fact Research

분석 항목: Issue Summary, Key Facts, Timeline, Current Status, 기관/인물/장소, Uncertainties, Missing Information, Source References.

```text
Search Results → 핵심 문서 선별 → 본문 추출 → Qwen Fact Synthesis → FactResearchResult
```

규칙: 확인된 사실과 향후 계획 구분 / 법안 발의·통과·공포·시행 구분 / 투자계획·MOU·집행 완료 구분 / 숫자·일정은 문서 근거에 연결 / 상충 자료는 임의 결론 금지 / 모든 주요 사실은 `source_result_ids`로 추적. **구현 상태: 완료, 회귀 검증 필요** (timeline 날짜 누락, 나머지 3개 이슈 v2 미실행)

### 4.5 Online Research — Discussion Analysis

Fact는 "무슨 일이 일어났는가", Discussion은 "그 사건과 관련해 무엇이 중요하게 다뤄지는가"다.

| Fact | Discussion |
|---|---|
| 특별법 국회 통과 | 폐지지역 경제 충격 대응 |
| 지원 근거 마련 | 노동자 고용 전환 대책 |
| 법률에 지원사업 규정 | 재정 지원과 대체산업 육성 |
| 발전소 폐쇄 일정 | 정의로운 전환·탈석탄 원칙 논란 |

방식: 관련 문서 수집 → 논점 후보 추출 → 유사 논점 통합 → 논점별 근거 문서 연결 → 검토 화면에서 포함/제외. 단순 사건 발표를 논점으로 중복 생성하지 않고, 문서에 없는 논점을 정책 상식으로 추가하지 않으며, 반복 언급을 시민의 지지·우려 확인으로 표현하지 않는다. **구현 상태: 완료, 최종 보고서 검증 필요**

### 4.6 Online Research — Reaction Analysis

문서에 나타난 평가·기대·우려·비판·요구·경험 등 명시적 반응을 추출한다.

```text
Online Documents → 1차 Qwen 반응 후보 → 근거 문장 존재 검증(코드) → 2차 Qwen 검증
  → Reaction Candidates → Human Review → Approved Reactions → Reaction Theme / Tone
```

규칙: 정책 설명·공식 발표를 시민 반응으로 해석하지 않음 / 기사 요약·보도자료 재게시는 반응이 아님 / 명시적 근거 없으면 제외 / 해당 지역·이슈와 직접 관련 / 무관한 일반 의견 제외.

| 승인 반응 수 | 분석 동작 |
|---|---|
| 0건 | 논점 정상 출력, 반응 부족 표시 |
| 1~2건 | 근거 원문 표시, 전체 여론 방향 판단 보류 |
| 3건 이상 | 반응 테마·톤 분석 허용 (대표성 확보를 뜻하지 않음) |

**구현 상태: 완료, Human Review 검증 필요**

### 4.7 Keyword Analysis

단순 빈도만으로 결정하지 않는다.

```text
Online Corpus + Discussion Topics → Keyword Candidates → 실제 문서 출현 검증 → Keyword Ranking
```

목표 예: `고용전환 / 정의로운 전환 / 대체산업 / 지역경제 / 통합본사 / 탈석탄` (일반 빈도 결과 `충남 / 지역 / 특별법 / …` 지양). 구현: 후보 추출, 유사 표현 정규화, 불용어·일반명사 제거, 논점 연계 선정, 출현 문서 수 집계, Top 10~20. LLM은 의미 판단, 빈도·문서 수는 코드 계산. 2.0의 형태소 기반 TOP10 재사용 가능성을 먼저 확인한다. **구현 상태: 다음 개발 단계**

### 4.8 Channel Analysis

채널별 관련 문서 수, 주요 논점(해당 채널 문서 3건 이상이 뒷받침할 때만), 확인된 반응, 반응 방향(승인 반응 3건 이상일 때만). 표본 수를 함께 표시하고 검색 결과의 특징을 채널 전체 이용자 성향으로 확대하지 않는다. **구현 상태: 완료, 보고서 연결 검증 필요**

### 4.9 Quantitative Analysis

채널별 수집·관련 문서 수, 일별·주별 추이, 기간별 비교, 이슈별 문서 수 비교, 키워드 빈도. Pandas 집계, 중복 제거 후 문서 단위. 검색 API 문서 수는 온라인 전체 언급량이 아니므로 **"수집 문서 기준 언급량"**으로 표기하고, 전월 대비는 동일 채널·검색 조건·수집 방식 자료에서만 비교한다. **구현 상태: 개발 예정**

### 4.10 Monthly Synthesis (V1 포함)

여러 이슈의 FactResearchResult·논점·승인 반응·정량 결과를 월간 보고서 하나로 합성한다. 이슈 간 내용을 섞지 않고 이슈별 근거 추적성을 유지하며, 종합 단계에서 새 사실·수치를 만들지 않는다(AGENTS.md 6·7번). 기존 2.0의 월간 보고서 요구사항(`docs/aiporg2/monthly-keyword-report-requirements.md`)과 HWPX 구성을 참고한다. **구현 상태: 미착수, 설계 필요**

## 5. Human Review 설계

AI가 정리한 결과를 담당자가 승인·제외하는 방식이다. 상태: `PENDING → APPROVED | REJECTED`. 반응 후보는 검토 완료 전까지 보고서의 확정 반응으로 쓰지 않는다.

- **Fact Review (V1 최소 기능):** 핵심 사실·수치, 일정·정책 현황, 원문 출처의 승인/제외 (핵심 사실·일정 해제 구현됨)
- **Discussion Review:** 논점 제목·요약·근거 문서, 포함/제외
- **Reaction Review:** 제목, 채널·URL, 반응 근거, AI 검증 사유, 사용/제외

현재 구현: 세션(`output/research/session_*.json`)을 불러오는 `streamlit_app/opinion_review.py` — 이슈별 논점 선택, 반응 후보 사용/제외, 검토 완료 확인, 승인 반응 기반 보고서 재생성. 테스트 이슈 3개(석탄화력 특별법, 기후살인 폭염 대응, 삼성디스플레이 67조 투자). **구현 상태: 논점·반응 기본 기능 완료**

## 6. Report Generation

입력: FactResearchResult, DiscussionTopics, ApprovedReactions, KeywordAnalysis, ChannelAnalysis, QuantitativeAnalysis.

구성: ① 이슈 개요·주요 현황 ② 주요 온라인 논점 ③ 온라인 반응·여론 표정(표본·한계 명시) ④ 주요 키워드 ⑤ 채널별 특징 ⑥ 언급량·추이 ⑦ 시사점. 월간 보고서는 이슈별 ①~⑦을 묶고 월간 종합을 덧붙인다.

**Grounded Generation:** 입력된 분석 결과에 근거해서만 작성한다.
- 허용: "발전소 폐지 이후 노동자 고용 전환이 주요 논점으로 나타났다."
- 금지: 반응 근거 없는 "주민 우려가 커지고 있다", 근거 없는 "경제 활성화 효과가 기대된다", 임의의 언급량·비율·감성 점수, 정책 발표를 시민의 긍정 평가로 전환.

출력: Markdown(원본·편집), HTML(미리보기), DOCX(제출·공유), HWPX(기존 시제품 유지). **구현 상태:** Markdown 재생성 가능, 나머지는 통합 검증 필요

## 7. 데이터 저장 및 실행 관리

| 데이터 | 역할 |
|---|---|
| Issue | 분석 대상 이슈와 기간 (※ 2.0 `Issue`와 이름 구분 필요) |
| SearchPlan | 조사 질문·검색 질의 |
| SearchResult | 채널별 수집 결과 |
| FetchedDocument | 추출된 문서 본문 |
| FactResearchResult | 핵심 사실·현황 |
| DiscussionTopic | 주요 논점과 근거 |
| ReactionCandidate | 반응 후보와 근거 |
| HumanReview | 승인·제외 결과 |
| KeywordResult | 키워드 분석 |
| ChannelInsight | 채널별 특징 |
| QuantitativeResult | 언급량·추이 |
| Report | 생성된 보고서 (※ 2.0 `Report`와 이름 구분 필요) |

**Stage Cache:** SearchPlan → SearchResult → FetchedDocument → FactResearchResult → Discussion/Reaction Candidates → Human Review → Report 순으로 단계 결과를 저장한다. 목표: 단계별 재실행, 프롬프트 변경 시 필요한 단계만 재분석, LLM 호출·시간 감소, 입력 동일 시 결과 비교, 실패 단계부터 재시작. MVP는 SQLite와 JSON 세션을 쓰고 별도 메시지 큐·분산 워크플로 엔진은 도입하지 않는다. 새 schema는 설계 승인 후 추가한다.

## 8. 개발 및 검증 로드맵

### Phase 1. 핵심 수집·분석 파이프라인 — 완료
Issue Input, Qwen Query Expansion, Naver/Daum 검색, 정규화·중복 제거, 관련도 필터, Article Fetcher, Fact Research, Discussion Extraction, Reaction Candidate Extraction, Reaction Evidence Verification.

### Phase 2. 여론 분석 및 검토 기능 — 진행 중
- [x] Discussion/Reaction 분리, 반응 표본별 처리, 채널별 논점, Human Review 기본 화면, 승인 반응 기반 재생성
- [ ] 기존 3개 이슈 검토 완료
- [ ] Reviewed Report 3개 생성
- [ ] 기존 수작업 보고서와 회귀 비교
- [ ] 사실·논점·반응 혼합 여부 점검

완료 조건: 근거 없는 여론을 생성하지 않으면서 수작업 보고서의 핵심 현황·논점을 재현한다.

### Phase 3. Keyword & Quantitative Analysis
- [x] 키워드 추출·정규화·빈도 검증 (V1: 제목+스니펫 기준, 품질은 이슈별로 편차 있음)
- [ ] 채널별 언급량, 일별·주별 추이, 시계열 그래프 데이터
- [ ] 보고서에 정량 결과 연결

완료 조건: 모든 수치가 수집 데이터에서 계산되고 수집 범위·집계 기준을 명시한다.

### Phase 4. Monthly Synthesis (신규)
- [ ] 다수 이슈 합성 설계(모델명·schema 승인)
- [ ] 이슈별 근거 추적 유지, 월간 종합 문장 생성
- [ ] 2.0 HWPX 구성과 연결
- [x] Fact Review 최소 화면(핵심 사실·일정을 출처와 함께 해제) — 요약·현재 상태 편집은 미지원
- (제외) 정보 공백 기반 반복 조사 루프는 V1 범위 밖

### Phase 5. End-to-End Regression
신규 지역 이슈 선정 → 검색부터 검토 화면까지 전체 실행 → Fact/Discussion/Reaction 품질 검증 → 단계별 시간 기록 → 오류 시 단계별 재실행 확인 → 최종 보고서 생성. 완료 조건: 추가 수동 조사 없이 검토 가능한 결과가 생성된다.

### Phase 6. Persistence & Performance
단계별 결과 저장, SQLite 모델 정리, Session 재개, Stage Cache·선택적 재실행, 중복 LLM 호출 최소화, 실행 로그·오류 상태 관리.

### Phase 7. Report Export & UI
Preview, Markdown/HTML/DOCX/HWPX Export, 표·그래프 삽입, 분석 완료 상태, 최종 다운로드. 2.0의 승인본 출력 버전 고정 문제(HANDOFF 남은 제약 1번)를 함께 해결한다.

## 9. 품질 평가 기준

- **Fact Accuracy:** 사건·날짜 정확, 수치와 정책 상태 비혼동, 주요 사실의 출처 연결
- **Discussion Coverage:** 중요 논점 포착, 단순 사실의 논점 중복 없음, 자료에 없는 논점 생성 없음
- **Reaction Precision:** 근거 존재, 정책 설명·정보 전달을 여론으로 오인하지 않음, 이슈와 직접 관련
- **Quantitative Reliability:** 실제 집계값, 중복 제거, 비교 가능한 데이터끼리 추이 계산, 표본 한계 명시
- **Report Grounding:** 사실·논점·반응 구분, 근거 없는 기대·우려·효과 없음, 시사점이 분석 결과에서 도출, 검토 결과가 최종본에 반영

## 10. MVP 완료 기준

1. 지역·기간·이슈 입력
2. 자동 검색·수집·중복 제거·정제
3. 핵심 사실·정책 현황을 출처와 함께 정리
4. 논점과 실제 반응 구분 분석
5. 담당자의 논점·반응 검토
6. 주요 키워드·채널별 특징 제공
7. 수집 문서 기준 언급량·추이 계산
8. 근거 없는 수치·여론 미생성
9. 분석 결과를 월간 보고서(다수 이슈 종합)로 자동 변환
10. Markdown·HTML·DOCX·HWPX 출력
11. 기존 분석 세션 재사용으로 불필요한 전체 재실행 방지

## 11. 향후 확장 방향

신규 수집 채널, 월별 이슈·키워드 변화 비교, 반복 보고서 스케줄링, 분석 이력 검색·재사용, 보고서 템플릿 관리, **PostgreSQL/pgvector 기반 다중 사용자 환경(임베딩 의미 중복 제거·논점 군집화 포함)과 워크플로 엔진 도입 — V1 안정화 이후 확정**.

초기에는 분석 체계 확장보다 수작업 보고서 작성 과정의 자동화 수준, 결과의 근거성, 실행 재현성을 우선한다.

## 12. 다음 구현 순서

1. 기존 세 이슈 Human Review 및 보고서 재생성
2. 수작업 보고서와 비교해 분석 품질 확정 (Phase 2 종료)
3. Keyword Analysis → Quantitative Analysis, 보고서 연결
4. Monthly Synthesis 설계·구현
5. 신규 이슈 End-to-End 테스트
6. Stage Cache·실행 이력 저장
7. UI 통합, DOCX·HTML·HWPX Export 마무리

**최종 지향점:** 사용자가 이슈를 선정하면 시스템이 조사, 사실 정리, 논점·반응 분석, 정량 분석, 월간 보고서 초안 작성까지 수행하고 담당자는 검토와 최종 확정에 집중한다.
