# Issue-driven Research & Analysis Engine

> Implementation-oriented PRD for Codex / Claude Code

## 0. Document Purpose

이 문서는 `Issue-driven Research & Analysis Engine`의 MVP 구현을 위한 기준 문서다.

Codex, Claude Code 또는 개발자는 구현 시 이 문서를 source of truth로 사용한다.

이 프로젝트의 핵심은 일반적인 뉴스 수집기나 이슈 자동 탐지 시스템이 아니다.

사용자가 직접 지정한 이슈에 대해 시스템이:

1. 검색 계획을 세우고
2. 웹을 검색하고
3. 실제 문서를 읽고
4. Fact와 Evidence를 추출하고
5. 현재 정보에서 부족한 내용을 판단하고
6. 필요한 경우 추가 검색을 반복하고
7. 공개 검색 가능한 온라인 반응을 별도로 분석하고
8. Fact와 Opinion을 결합하여
9. 근거 기반 보고서를 생성하는 것

이 목표다.

---

# 1. Product Definition

## 1.1 Product Name

Working name:

`IssueScope`

제품명은 추후 변경 가능하다.

---

## 1.2 One-line Definition

사용자가 지정한 핵심 이슈를 AI가 반복적으로 조사·검증하고 공개 온라인 반응을 분석하여 근거 기반 이슈 분석 보고서를 생성하는 Issue-driven Research & Analysis Engine.

---

# 2. Core Principle

가장 중요한 제품 원칙:

> Human selects the issue. AI researches the issue.

사용자가 분석 대상 이슈를 직접 입력한다.

AI가 이번 달의 주요 이슈를 자동으로 선정하는 것은 MVP 범위가 아니다.

예:

```json
{
  "region": "충청남도",
  "start_date": "2026-09-01",
  "end_date": "2026-09-30",
  "issues": [
    "공공기관 충남 2차 이전·내포신도시",
    "충남 재정전략회의",
    "인사청문특위 부적격 판단 전격 수용",
    "삼성디스플레이 67조 투자"
  ]
}
```

---

# 3. Problem Statement

현재 정책/지역/산업 이슈 분석은 다음과 같은 수작업을 필요로 한다.

```text
Issue Selection
    ↓
Search
    ↓
Article Reading
    ↓
Fact Collection
    ↓
Additional Questions
    ↓
Re-search
    ↓
Fact Verification
    ↓
Public Reaction Search
    ↓
Sentiment / Frame Analysis
    ↓
Keyword Analysis
    ↓
Insight Generation
    ↓
Source Organization
    ↓
Report Writing
```

특히 중요한 문제는 검색 한 번으로 분석에 필요한 정보가 모두 확보되지 않는다는 점이다.

예:

```text
Issue
삼성디스플레이 67조 투자
```

초기 검색 이후 다음과 같은 추가 질문이 발생할 수 있다.

```text
- 67조 원은 일시 투자 또는 장기 투자 계획인가?
- 실제 투자 기간은 언제까지인가?
- 어느 지역에 생산라인이 구축되는가?
- 충청남도는 무엇을 지원하는가?
- 전력과 용수는 어떻게 공급되는가?
- 지역 일자리 효과는 무엇인가?
- 지역 협력기업과의 연계 계획은 존재하는가?
```

따라서 시스템은 단순 `Search → Summary`가 아니라 반복적인 Research Loop를 가져야 한다.

---

# 4. Primary Goals

## G1. Iterative Research

현재 확보한 정보를 기준으로 부족한 정보를 탐지하고 추가 검색한다.

```text
Issue
 ↓
Query Generation
 ↓
Search
 ↓
Read
 ↓
Fact Extraction
 ↓
Knowledge Update
 ↓
Missing Information Detection
 ↓
Need More?
 ├─ YES → Query Generation
 └─ NO  → Research Complete
```

---

## G2. Evidence-grounded Facts

LLM 자체 지식을 Fact source로 사용하지 않는다.

모든 주요 Fact는 실제 Source와 연결되어야 한다.

```text
Source Document
      ↓
Evidence
      ↓
Fact
      ↓
Analysis
      ↓
Report
```

최종 Report의 주요 주장으로부터 원문 Source까지 역추적 가능해야 한다.

---

## G3. Separate Fact and Opinion

사실조사와 온라인 반응 분석을 별도의 파이프라인으로 처리한다.

```text
                Issue
                  │
          ┌───────┴───────┐
          ▼               ▼
    Fact Research    Opinion Research
          │               │
          └───────┬───────┘
                  ▼
             Synthesis
```

---

## G4. Structured Analysis

온라인 반응은 단순 Positive / Negative 분류로 끝내지 않는다.

기본 분석 단위:

```text
Target
+
Sentiment
+
Frame
+
Reason
```

---

# 5. Non-goals

MVP에서 구현하지 않는다.

- 자동 월간 이슈 발굴
- BERTopic
- HDBSCAN
- UMAP
- 전체 뉴스 클러스터링
- Issue Ranking
- SNS 전체 크롤링
- 실시간 Social Listening
- 자체 NLP 모델 학습
- 대규모 Vector DB
- 복잡한 Multi-Agent architecture
- Airflow
- Kafka
- 자체 Search Engine

향후 확장 가능하지만 현재 구현에 포함하지 않는다.

---

# 6. Target Users

Primary:

- 지자체 정책 담당자
- 지자체 홍보 담당자
- 공공기관 리서치 담당자

Secondary:

- 정책 연구기관
- 컨설팅
- 기업 PR/대외협력
- 산업 리서치 담당자

향후 다른 분야로 확장할 수 있도록 특정 지역이나 기관을 코드에 하드코딩하지 않는다.

---

# 7. Main User Flow

## 7.1 Create Analysis

사용자가 입력한다.

```text
Analysis Name
Region
Start Date
End Date
Issues[]
```

Example:

```text
Analysis Name:
2026년 9월 충남 온라인 여론 분석

Region:
충청남도

Period:
2026-09-01 ~ 2026-09-30

Issues:
1. 공공기관 충남 2차 이전·내포신도시
2. 충남 재정전략회의
3. 인사청문특위 부적격 판단 전격 수용
4. 삼성디스플레이 67조 투자
```

---

## 7.2 Start Analysis

각 Issue를 독립적으로 처리한다.

```text
Analysis
 ├─ Issue 1 → research_issue()
 ├─ Issue 2 → research_issue()
 ├─ Issue 3 → research_issue()
 └─ Issue 4 → research_issue()
```

Issue 간 병렬 실행이 가능하도록 설계한다.

MVP에서 반드시 병렬 처리할 필요는 없지만 architecture는 Issue 간 독립성을 유지한다.

---

## 7.3 Research Issue

각 Issue:

```text
Research Plan
↓
Initial Search
↓
Document Collection
↓
Fact Extraction
↓
Knowledge Merge
↓
Missing Information Detection
↓
Follow-up Search
↓
Research Complete
```

---

## 7.4 Analyze Public Reaction

Research 완료 이후:

```text
Reaction Query Generation
↓
Public Web Search
↓
Channel Classification
↓
Opinion Extraction
↓
Aspect Analysis
↓
Sentiment
↓
Frame
↓
Reason
↓
Keyword Extraction
```

---

## 7.5 Generate Report

모든 Issue 결과를 합쳐:

```text
Executive Summary
Issue Analysis
Public Reaction
Sentiment
Positive Drivers
Negative Drivers
Keywords
Implications
Channel Strategy
Sources
```

를 생성한다.

---

# 8. System Architecture

논리적으로 3개 Engine으로 분리한다.

```text
┌──────────────────────────────┐
│ 1. Issue Research Engine     │
└──────────────┬───────────────┘
               ↓
      Verified Issue Knowledge
               ↓
┌──────────────────────────────┐
│ 2. Opinion Analysis Engine   │
└──────────────┬───────────────┘
               ↓
        Issue Analysis
               ↓
┌──────────────────────────────┐
│ 3. Report Synthesis Engine   │
└──────────────┬───────────────┘
               ↓
          Final Report
```

세 Engine을 반드시 별도 서비스로 배포할 필요는 없다.

MVP에서는 하나의 FastAPI application 내부 module/service로 구현한다.

---

# 9. Recommended Project Structure

```text
app/
├── main.py
│
├── api/
│   ├── analyses.py
│   ├── issues.py
│   └── reports.py
│
├── core/
│   ├── config.py
│   ├── database.py
│   └── logging.py
│
├── models/
│   ├── analysis.py
│   ├── issue.py
│   ├── document.py
│   ├── fact.py
│   ├── opinion.py
│   └── report.py
│
├── schemas/
│   ├── analysis.py
│   ├── research.py
│   ├── fact.py
│   ├── opinion.py
│   └── report.py
│
├── services/
│   ├── research/
│   │   ├── planner.py
│   │   ├── query_generator.py
│   │   ├── search_service.py
│   │   ├── document_reader.py
│   │   ├── fact_extractor.py
│   │   ├── knowledge_merger.py
│   │   ├── gap_detector.py
│   │   └── orchestrator.py
│   │
│   ├── opinion/
│   │   ├── query_generator.py
│   │   ├── channel_classifier.py
│   │   ├── sentiment_analyzer.py
│   │   ├── frame_analyzer.py
│   │   ├── keyword_extractor.py
│   │   └── orchestrator.py
│   │
│   ├── report/
│   │   ├── issue_synthesizer.py
│   │   ├── monthly_synthesizer.py
│   │   └── renderer.py
│   │
│   └── llm/
│       ├── client.py
│       ├── prompts.py
│       └── structured_output.py
│
├── repositories/
│
├── prompts/
│
├── tests/
│
└── migrations/
```

이 구조는 권장안이다.

현재 repository 구조가 이미 존재한다면 무조건 이 구조로 변경하지 말고 기존 convention을 우선한다.

---

# 10. Issue Research Engine

## 10.1 Input

```json
{
  "region": "충청남도",
  "start_date": "2026-09-01",
  "end_date": "2026-09-30",
  "issue": "삼성디스플레이 67조 투자"
}
```

---

# 11. Research Plan

LLM을 이용해 초기 검색 계획을 생성한다.

Query를 목적별로 분류한다.

Enum:

```text
FACT
DETAIL
IMPACT
CONCERN
REACTION
BACKGROUND
```

### FACT

사건 자체 확인.

```text
삼성디스플레이 67조 투자 충남
삼성디스플레이 아산 MOU
```

### DETAIL

구체적인 사업 내용.

```text
아산디스플레이시티2 신규 생산라인
```

### IMPACT

지역 영향.

```text
삼성디스플레이 아산 일자리
삼성디스플레이 충남 지역경제
```

### CONCERN

우려 및 과제.

```text
삼성디스플레이 투자 전력 용수
```

### REACTION

온라인 반응.

```text
삼성디스플레이 67조 반응
아산 삼성 투자 기대
```

### BACKGROUND

현재 분석 기간 이전의 배경 자료.

---

# 12. Query Generation Output

LLM은 반드시 Structured Output을 반환한다.

Example:

```json
{
  "queries": [
    {
      "query": "삼성디스플레이 67조 투자 충남",
      "type": "FACT",
      "purpose": "투자 계획의 기본 사실 확인"
    },
    {
      "query": "삼성디스플레이 아산 일자리",
      "type": "IMPACT",
      "purpose": "지역 고용 효과 확인"
    }
  ]
}
```

자연어 문자열을 parsing하는 방식은 피한다.

---

# 13. Web Search

Search provider는 interface로 추상화한다.

```python
class SearchProvider:
    async def search(
        self,
        query: str,
        start_date: date | None,
        end_date: date | None,
        limit: int
    ) -> list[SearchResult]:
        ...
```

특정 Search API에 business logic을 결합하지 않는다.

향후 provider 교체가 가능해야 한다.

---

# 14. Search Result Schema

```json
{
  "query_id": "...",
  "title": "...",
  "url": "...",
  "domain": "...",
  "published_at": "...",
  "snippet": "...",
  "rank": 1
}
```

중복 URL은 제거한다.

Canonical URL을 가능하면 저장한다.

---

# 15. Date Filtering

기본 분석 자료:

```text
start_date <= published_at <= end_date
```

분석 기간 이전의 문서가 필요하면:

```text
source_role = BACKGROUND
```

로 저장한다.

Background source와 analysis-period source를 구분한다.

---

# 16. Document Reader

검색 결과 snippet만으로 Fact를 확정하지 않는다.

Pipeline:

```text
Search Result
↓
URL Fetch
↓
HTML Parsing
↓
Main Content Extraction
↓
Document
```

Document fields:

```text
id
url
canonical_url
title
publisher
author
published_at
body
fetched_at
fetch_status
source_role
```

---

# 17. Fetch Status

Enum:

```text
PENDING
SUCCESS
FAILED
BLOCKED
PARTIAL
```

본문 확보에 실패한 Search Result도 DB에서 삭제하지 않는다.

단:

```text
body_verified = false
```

상태로 관리한다.

본문 검증이 되지 않은 자료는 핵심 Fact Evidence로 사용하는 것을 제한한다.

---

# 18. Fact Extraction

LLM Structured Output을 사용한다.

Expected schema:

```json
{
  "facts": [
    {
      "subject": "삼성디스플레이",
      "predicate": "투자 계획",
      "object": "67조 원",
      "status": "PLANNED",
      "date": null,
      "confidence": 0.95,
      "evidence_text": "..."
    }
  ]
}
```

Fact는 반드시 해당 Document에서 확인할 수 있어야 한다.

LLM의 기존 지식을 Fact에 추가해서는 안 된다.

---

# 19. Evidence Model

Fact와 Evidence는 별도로 저장한다.

```text
Fact
 ├─ Evidence 1
 ├─ Evidence 2
 └─ Evidence 3
```

Evidence:

```text
id
fact_id
document_id
excerpt
start_offset
end_offset
```

offset 확보가 어려운 경우 MVP에서는 nullable하게 허용한다.

`excerpt`는 반드시 원문에서 추출한다.

---

# 20. Fact Verification

Fact 상태:

```text
EXTRACTED
SUPPORTED
VERIFIED
CONFLICTED
REJECTED
```

Recommended logic:

```text
1 source
→ SUPPORTED

2+ independent reliable sources
→ VERIFIED

contradictory reliable sources
→ CONFLICTED
```

단, 공식기관 자료처럼 단일 authoritative source가 충분한 경우 VERIFIED로 승격할 수 있도록 설계한다.

---

# 21. Source Reliability

Source Type:

```text
OFFICIAL
NEWS
SPECIALIZED_MEDIA
BLOG
COMMUNITY
SOCIAL
OTHER
```

Fact Research 우선순위:

```text
OFFICIAL
>
NEWS
>
SPECIALIZED_MEDIA
>
Others
```

Opinion Research에서는 BLOG / COMMUNITY / SOCIAL도 적극 활용한다.

Source reliability와 sentiment는 별개의 개념이다.

---

# 22. Issue Knowledge

각 Issue에 대해 현재까지 확인된 Knowledge를 구성한다.

```json
{
  "issue_id": "...",
  "verified_facts": [],
  "supported_facts": [],
  "conflicted_facts": [],
  "organizations": [],
  "people": [],
  "locations": [],
  "numbers": [],
  "dates": [],
  "sources": []
}
```

이 객체는 매 iteration마다 갱신된다.

---

# 23. Missing Information Detection

Research Engine의 핵심 기능이다.

현재 Issue Knowledge를 LLM에 제공하고 다음을 판단한다.

```text
이 이슈를 충분히 분석하기 위해
아직 확인되지 않은 중요한 정보는 무엇인가?
```

Expected output:

```json
{
  "missing_information": [
    {
      "topic": "투자 기간",
      "reason": "67조 원 투자 계획의 실행 기간이 확인되지 않음",
      "priority": "HIGH"
    },
    {
      "topic": "전력·용수 확보 방안",
      "reason": "대규모 생산시설 운영에 필요한 인프라 정보 부족",
      "priority": "MEDIUM"
    }
  ]
}
```

Priority:

```text
HIGH
MEDIUM
LOW
```

---

# 24. Follow-up Query Generation

Missing Information을 검색 Query로 변환한다.

```text
Missing Information
↓
Query
↓
Search
↓
Document
↓
Fact
↓
Knowledge Update
```

예:

```text
투자 기간
→ "삼성디스플레이 67조 투자 기간"

전력·용수
→ "삼성디스플레이 아산 전력 용수 지원"
```

---

# 25. Research Loop

Pseudo code:

```python
async def research_issue(issue):
    knowledge = IssueKnowledge()

    queries = await generate_initial_queries(issue)

    for iteration in range(MAX_RESEARCH_ITERATIONS):
        search_results = await search(queries)

        documents = await fetch_documents(search_results)

        facts = await extract_facts(documents)

        knowledge = await merge_knowledge(
            knowledge,
            facts,
        )

        gaps = await detect_missing_information(
            issue,
            knowledge,
        )

        if research_is_complete(knowledge, gaps):
            break

        queries = await generate_followup_queries(
            issue,
            gaps,
        )

    return knowledge
```

---

# 26. Research Completeness

Research 완료 여부를 LLM 판단 하나에만 의존하지 않는다.

Checklist 기반 deterministic evaluation을 함께 사용한다.

Required dimensions:

```text
BACKGROUND
DATE
CORE_CONTENT
ORGANIZATIONS
KEY_NUMBERS
LOCAL_ROLE
EXPECTED_IMPACT
CONCERNS
FUTURE_PLAN
SOURCES
```

Example:

```json
{
  "background": true,
  "date": true,
  "core_content": true,
  "organizations": true,
  "key_numbers": true,
  "local_role": true,
  "expected_impact": true,
  "concerns": false,
  "future_plan": true,
  "trusted_source_count": 4
}
```

---

# 27. Research Status

```text
PENDING
RESEARCHING
NEED_MORE
COMPLETE
INCOMPLETE
FAILED
```

`INCOMPLETE`는 최대 iteration에 도달했지만 필수 정보가 충분하지 않은 경우 사용한다.

AI가 부족한 정보를 임의로 생성해서 COMPLETE로 만들면 안 된다.

---

# 28. Research Limits

환경변수 또는 config로 관리한다.

Initial recommended defaults:

```env
MAX_RESEARCH_ITERATIONS=3
MAX_INITIAL_QUERIES=10
MAX_FOLLOWUP_QUERIES=8
MAX_RESULTS_PER_QUERY=10
MAX_DOCUMENTS_PER_ISSUE=50
```

숫자는 운영하면서 변경 가능해야 한다.

코드에 magic number로 흩어놓지 않는다.

---

# 29. Opinion Analysis Engine

Fact Research와 별도로 실행한다.

Input:

```text
Issue
+
Verified Issue Knowledge
```

---

# 30. Reaction Query Generation

예:

```text
삼성디스플레이 67조 기대
삼성디스플레이 67조 우려
아산 삼성 투자 반응
삼성디스플레이 지역경제
삼성 투자 일자리 아산
```

Fact Query와 Opinion Query를 DB에서도 구분한다.

---

# 31. Important Interpretation Rule

본 시스템은 전체 SNS 게시물을 수집하지 않는다.

따라서 결과를:

```text
전체 온라인 여론
```

이라고 표현하지 않는다.

기본 표현:

```text
공개 검색 가능한 온라인 콘텐츠 기준
```

Internal naming:

```text
public_search_results
indexed_public_mentions
```

`total_mentions`와 같이 전체 모집단을 의미하는 변수명을 사용하지 않는다.

---

# 32. Channel Classification

Enum:

```text
NEWS
X
YOUTUBE
BLOG
COMMUNITY
CAFE
INSTAGRAM
OTHER
```

domain 및 metadata 기반으로 우선 분류한다.

필요한 경우 LLM classification을 fallback으로 사용한다.

---

# 33. Public Content Schema

```json
{
  "id": "...",
  "issue_id": "...",
  "channel": "YOUTUBE",
  "title": "...",
  "text": "...",
  "url": "...",
  "published_at": "...",
  "source_type": "SOCIAL"
}
```

---

# 34. Opinion Analysis Unit

분석 단위:

```text
Target
+
Sentiment
+
Frame
+
Reason
```

Expected schema:

```json
{
  "aspects": [
    {
      "target": "삼성디스플레이 투자",
      "sentiment": "POSITIVE",
      "frame": "ECONOMIC_GROWTH",
      "reason": "지역경제 활성화 기대",
      "confidence": 0.91
    }
  ]
}
```

---

# 35. Aspect-based Sentiment

하나의 콘텐츠가 여러 Target에 대해 서로 다른 감성을 가질 수 있다.

Example input:

```text
부적격 의견을 받아들인 것은 잘했지만
애초에 이런 후보자를 추천한 것은 문제다.
```

Output:

```json
{
  "aspects": [
    {
      "target": "부적격 의견 수용",
      "sentiment": "POSITIVE",
      "frame": "COOPERATION"
    },
    {
      "target": "후보자 추천",
      "sentiment": "NEGATIVE",
      "frame": "PERSONNEL_VERIFICATION"
    }
  ]
}
```

콘텐츠 하나당 sentiment 하나만 강제로 부여하지 않는다.

---

# 36. Sentiment Enum

```text
POSITIVE
NEGATIVE
NEUTRAL
MIXED
```

`MIXED`는 content-level summary에 사용할 수 있다.

Aspect level에서는 가능하면 Positive / Negative / Neutral 중 하나를 사용한다.

---

# 37. Initial Frame Taxonomy

## Positive

```text
ECONOMIC_GROWTH
EMPLOYMENT
REGIONAL_BALANCE
POLICY_INNOVATION
SAFETY_IMPROVEMENT
COOPERATION
INTERNATIONAL_STATUS
INDUSTRIAL_COMPETITIVENESS
```

## Negative

```text
EMPLOYMENT_RISK
REGIONAL_ECONOMIC_DECLINE
FISCAL_CONCERN
POLICY_UNCERTAINTY
PERSONNEL_VERIFICATION
DISASTER_DAMAGE
FEASIBILITY
REGIONAL_CONFLICT
```

## Neutral

```text
WAIT_AND_SEE
SCHEDULE_CHECK
POLICY_INFORMATION
WAITING_FOR_RESULT
```

DB에는 enum code와 display label을 분리한다.

Example:

```json
{
  "code": "ECONOMIC_GROWTH",
  "label_ko": "경제성장"
}
```

향후 taxonomy를 DB 기반으로 변경할 수 있도록 확장 가능성을 유지한다.

---

# 38. Keyword Extraction

Keyword source:

```text
Verified Facts
+
Fact Documents
+
Public Reaction
```

LLM은 동의어와 중복 표현을 정규화한다.

Example:

```text
삼성 투자
삼성디스플레이 투자
67조 투자
```

필요 시:

```text
삼성디스플레이 67조 투자
```

로 merge한다.

---

# 39. Keyword Score

MVP에서는 복잡한 ML ranking을 만들지 않는다.

다음 신호를 조합한다.

```text
frequency
issue_relevance
source_diversity
cross_issue_frequency
search_exposure
```

최종적으로 Issue Keyword와 Monthly Top Keyword를 생성한다.

---

# 40. Report Synthesis Engine

Report는 기존 LLM 지식이 아니라 저장된 Analysis Data만을 기반으로 생성한다.

Input:

```text
Issue Knowledge
Opinion Analysis
Keywords
Sources
```

---

# 41. Issue Report Structure

각 Issue:

```text
1. 핵심 내용
2. 주요 사실
3. 현재 상황
4. 공개 온라인 반응
5. 긍정 반응 원인
6. 부정/우려 반응 원인
7. 핵심 키워드
8. 시사점
9. 출처
```

---

# 42. Monthly Report Structure

```text
1. Executive Summary

2. 주요 이슈 분석
   2.1 Issue A
   2.2 Issue B
   2.3 Issue C
   2.4 Issue D

3. 공개 온라인 반응 분석

4. 감성 분석

5. 긍정 여론 주요 원인

6. 부정 여론 주요 원인

7. 핵심 키워드 Top 20

8. 핵심 시사점

9. 채널별 대응전략

10. Sources
```

---

# 43. Insight Generation Rule

시사점은 단순 요약이 아니다.

반드시 다음 reasoning structure를 사용한다.

```text
Current Evaluation
        ↓
Unresolved Problem
        ↓
Recommended Response
        ↓
Future Outcome / Metric
```

Example:

```text
현재 평가:
대규모 투자 기대

미해결 과제:
투자가 장기간 단계적으로 진행됨

정책 대응:
전력·용수 등 기반시설 지원

향후 성과:
지역 일자리 및 지역기업 성장
```

Result:

```text
대규모 투자계획을 일자리·기업 성장 등
지역 체감성과로 연결할 필요가 있음.
```

---

# 44. Channel Strategy

각 Channel에 대해 다음을 계산/요약한다.

```text
dominant_issues
dominant_frames
common_questions
common_concerns
content_behavior
```

이 데이터를 기반으로 전략을 생성한다.

Example:

```json
{
  "channel": "X",
  "dominant_issues": ["삼성 67조", "공공기관 이전"],
  "dominant_frames": ["경제성장", "정책불확실성"],
  "common_concerns": ["실제 투자 시점", "이전 일정"],
  "recommended_strategy": "핵심 수치와 진행상황을 짧은 카드형 콘텐츠로 제공"
}
```

---

# 45. Source Generation

Report Sources는 실제 사용된 Evidence를 기준으로 생성한다.

Source entry:

```text
publisher
published_at
title
used_for
url
```

Report option:

```text
show_source_url = true | false
```

URL을 최종 보고서에서 숨기더라도 DB에는 항상 저장한다.

---

# 46. API Requirements

## Create Analysis

```http
POST /api/v1/analyses
```

Request:

```json
{
  "name": "2026년 9월 충남 온라인 여론 분석",
  "region": "충청남도",
  "start_date": "2026-09-01",
  "end_date": "2026-09-30",
  "issues": [
    "공공기관 충남 2차 이전·내포신도시",
    "충남 재정전략회의",
    "인사청문특위 부적격 판단 전격 수용",
    "삼성디스플레이 67조 투자"
  ]
}
```

---

## Get Analysis

```http
GET /api/v1/analyses/{analysis_id}
```

---

## List Issues

```http
GET /api/v1/analyses/{analysis_id}/issues
```

---

## Get Issue

```http
GET /api/v1/issues/{issue_id}
```

---

## Start Research

```http
POST /api/v1/issues/{issue_id}/research
```

---

## Retry Research

```http
POST /api/v1/issues/{issue_id}/retry
```

---

## Get Facts

```http
GET /api/v1/issues/{issue_id}/facts
```

---

## Get Sources

```http
GET /api/v1/issues/{issue_id}/sources
```

---

## Get Opinions

```http
GET /api/v1/issues/{issue_id}/opinions
```

---

## Generate Report

```http
POST /api/v1/analyses/{analysis_id}/reports
```

---

## Get Report

```http
GET /api/v1/reports/{report_id}
```

---

# 47. Core Database Entities

Minimum entities:

```text
analyses
issues

search_queries
search_results

documents

facts
fact_evidences

research_iterations
research_gaps

public_contents
opinion_aspects

keywords

reports
report_sections
```

---

# 48. Entity Relationships

```text
Analysis
│
├── Issue
│   │
│   ├── SearchQuery
│   │     └── SearchResult
│   │           └── Document
│   │
│   ├── Fact
│   │     └── FactEvidence
│   │           └── Document
│   │
│   ├── ResearchIteration
│   │
│   ├── ResearchGap
│   │
│   ├── PublicContent
│   │     └── OpinionAspect
│   │
│   └── Keyword
│
└── Report
      └── ReportSection
```

---

# 49. Analysis Table

Minimum fields:

```text
id
name
region
start_date
end_date
status
created_at
updated_at
```

---

# 50. Issue Table

```text
id
analysis_id
title
status
research_completeness
created_at
updated_at
```

---

# 51. Search Query Table

```text
id
issue_id
iteration_id
query
query_type
purpose
created_at
```

---

# 52. Document Table

```text
id
url
canonical_url
title
publisher
author
published_at
body
source_type
source_role
fetch_status
fetched_at
```

Consider content hash for duplicate detection.

---

# 53. Fact Table

```text
id
issue_id
subject
predicate
object
status
fact_status
confidence
created_at
```

---

# 54. Fact Evidence Table

```text
id
fact_id
document_id
excerpt
start_offset
end_offset
created_at
```

---

# 55. Research Gap Table

```text
id
issue_id
iteration_id
topic
reason
priority
status
created_at
resolved_at
```

Status:

```text
OPEN
RESOLVED
UNRESOLVED
```

---

# 56. Public Content Table

```text
id
issue_id
document_id
channel
title
text
url
published_at
created_at
```

---

# 57. Opinion Aspect Table

```text
id
public_content_id
target
sentiment
frame
reason
confidence
created_at
```

---

# 58. LLM Architecture

LLM provider를 application logic에서 분리한다.

Recommended interface:

```python
class LLMClient:
    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        ...
```

특정 vendor SDK를 research service 곳곳에서 직접 호출하지 않는다.

---

# 59. LLM Tasks

LLM 사용 범위:

```text
Research Plan Generation
Query Generation
Fact Extraction
Fact Normalization
Knowledge Merge assistance
Missing Information Detection
Follow-up Query Generation

Opinion Aspect Extraction
Sentiment Analysis
Frame Classification
Reason Extraction

Keyword Normalization

Issue Synthesis
Monthly Synthesis
Insight Generation
Channel Strategy
```

---

# 60. LLM Grounding Rule

다음은 금지한다.

```text
Prompt:
"삼성디스플레이 투자에 대해 설명해줘"

→ LLM memory 기반 Fact 저장
```

반드시 retrieved content를 입력으로 제공한다.

```text
Retrieved Document
+
Task Instruction
↓
Structured Output
```

---

# 61. Structured Output

가능한 모든 LLM task는 Pydantic schema를 사용한다.

Bad:

```python
result = await llm("분석해줘")
parse_somehow(result)
```

Preferred:

```python
result = await llm.generate_structured(
    system_prompt=...,
    user_prompt=...,
    response_model=FactExtractionResult,
)
```

---

# 62. Prompt Management

Prompt를 Python service code 내부에 긴 문자열로 흩어놓지 않는다.

예:

```text
prompts/
├── research_plan.md
├── fact_extraction.md
├── gap_detection.md
├── reaction_query.md
├── opinion_analysis.md
├── keyword_normalization.md
├── issue_synthesis.md
└── monthly_synthesis.md
```

Prompt version을 추적할 수 있도록 설계한다.

---

# 63. Technology Stack

## Backend

```text
Python
FastAPI
Pydantic
SQLAlchemy
Alembic
```

## Database

```text
PostgreSQL
```

## LLM

Provider abstraction.

실제 provider/model은 환경변수로 변경 가능하게 한다.

## Search

External Web Search API.

Provider abstraction 필수.

## Article Reader

HTTP fetch + article/main-content extraction.

Provider 또는 parser 교체 가능하게 구현한다.

---

# 64. Optional Infrastructure

MVP 초기에는 필요하지 않다.

추후 필요 시:

```text
Redis
Celery / RQ
pgvector
```

를 추가한다.

처음부터 불필요하게 infrastructure를 복잡하게 만들지 않는다.

---

# 65. Frontend

MVP는 관리용 dashboard 형태로 구현한다.

Framework가 정해지지 않았다면:

```text
Next.js
TypeScript
```

를 권장한다.

단, 기존 repository에 frontend stack이 존재한다면 기존 stack을 우선한다.

---

# 66. Required Screens

## Analysis List

표시:

```text
Analysis Name
Period
Region
Issue Count
Status
Created At
```

---

## New Analysis

Fields:

```text
Analysis Name
Region
Start Date
End Date
Issues[]
```

---

## Analysis Detail

Issue별:

```text
Issue Name
Research Status
Research Completeness
Source Count
Fact Count
Open Gap Count
Opinion Count
```

---

## Issue Detail

Tabs:

```text
Overview
Facts
Public Reaction
Keywords
Sources
Research Log
```

---

## Research Monitor

Example:

```text
Research Completeness: 82%

Facts: 14
Sources: 21
Open Gaps: 2

Current Task:
전력·용수 인프라 지원 계획 조사

Timeline:

✓ Initial Queries
✓ Search
✓ Document Fetch
✓ Fact Extraction
✓ Gap Detection
● Follow-up Search
○ Opinion Analysis
○ Complete
```

---

## Report View

Sections:

```text
Executive Summary
Issue Analysis
Sentiment
Positive Drivers
Negative Drivers
Keywords
Implications
Channel Strategy
Sources
```

---

# 67. Report Export

MVP priority:

```text
P0: Markdown
P0: HTML
P1: DOCX
P2: PDF
P2: PPTX
```

Report generation logic과 file rendering logic을 분리한다.

---

# 68. Error Handling

## Search Failure

Query 단위로 retry 가능하게 한다.

전체 Issue research를 즉시 실패시키지 않는다.

---

## Fetch Failure

Document:

```text
fetch_status = FAILED
```

Search Result는 유지한다.

---

## LLM Failure

Structured output validation 실패 시 제한된 횟수만 retry한다.

무한 retry 금지.

---

## Insufficient Research

최대 iteration 이후에도 부족하면:

```text
status = INCOMPLETE
```

로 종료한다.

Report에는 부족한 정보가 있음을 명시한다.

---

## Source Conflict

충돌하는 Fact를 삭제하지 않는다.

```text
fact_status = CONFLICTED
```

로 보존한다.

Report 생성 시 확정 사실처럼 표현하지 않는다.

---

# 69. Observability

최소한 다음을 기록한다.

```text
analysis_id
issue_id
iteration
query
search result count
document fetch result
fact count
gap count
LLM task
LLM latency
token usage if available
error
```

Research 과정 전체를 debugging할 수 있어야 한다.

---

# 70. Cost Control

외부 Search 및 LLM API 호출이 반복되므로 비용 제어가 필요하다.

Implement:

```text
query deduplication
URL deduplication
document cache
LLM result cache where safe
max iteration
max queries
max documents
```

동일 Issue에서 동일 URL을 반복 fetch하지 않는다.

---

# 71. Security

API key를 repository에 commit하지 않는다.

Environment variables 사용:

```env
DATABASE_URL=
LLM_API_KEY=
SEARCH_API_KEY=
```

`.env.example`만 repository에 포함한다.

기사 원문 또는 외부 콘텐츠를 로그에 무제한 출력하지 않는다.

---

# 72. Testing Requirements

## Unit Tests

최소:

```text
Query generation schema validation
URL deduplication
Date filtering
Document normalization
Fact schema validation
Research completeness calculation
Channel classification
Sentiment schema validation
Keyword normalization
```

---

## Integration Tests

Mock Search Provider + Mock LLM Provider를 이용해:

```text
Issue
→ Query
→ Search
→ Document
→ Fact
→ Gap
→ Follow-up Query
→ Complete
```

전체 Research Loop를 검증한다.

---

# 73. Critical Test Scenario

Input:

```json
{
  "region": "충청남도",
  "start_date": "2026-09-01",
  "end_date": "2026-09-30",
  "issues": ["삼성디스플레이 67조 투자"]
}
```

Expected flow:

```text
Create Analysis
↓
Create Issue
↓
Generate Initial Queries
↓
Search
↓
Fetch Documents
↓
Extract Facts
↓
Create Evidence
↓
Merge Knowledge
↓
Detect Missing Information
↓
Generate Follow-up Queries
↓
Search Again
↓
Update Knowledge
↓
Research Complete / Incomplete
↓
Reaction Search
↓
Opinion Analysis
↓
Keyword Extraction
↓
Issue Synthesis
↓
Report Generation
```

---

# 74. MVP Acceptance Criteria

MVP 완료 조건:

### AC-01

사용자가 Region / Period / Issues를 입력해 Analysis를 생성할 수 있다.

### AC-02

각 Issue에 대해 자동으로 목적별 Search Query가 생성된다.

### AC-03

실제 Search Result를 가져올 수 있다.

### AC-04

Search Result URL의 본문을 수집할 수 있다.

### AC-05

본문에서 Structured Fact를 추출할 수 있다.

### AC-06

모든 주요 Fact가 Evidence와 연결된다.

### AC-07

현재 Knowledge에서 Missing Information을 탐지할 수 있다.

### AC-08

Missing Information을 기반으로 추가 Query를 생성하고 재검색한다.

### AC-09

Research 종료조건에 따라 COMPLETE 또는 INCOMPLETE를 결정한다.

### AC-10

Fact Research와 Opinion Research가 분리되어 있다.

### AC-11

공개 온라인 콘텐츠를 Channel별로 분류한다.

### AC-12

Target / Sentiment / Frame / Reason을 구조화하여 저장한다.

### AC-13

이슈별 Keyword를 생성한다.

### AC-14

여러 Issue 결과를 하나의 Analysis Report로 합성한다.

### AC-15

Report의 주요 Fact를 Evidence 및 Source까지 역추적할 수 있다.

### AC-16

Markdown 또는 HTML Report를 생성할 수 있다.

---

# 75. Development Phases

한 번에 전체 시스템을 구현하지 않는다.

## Phase 1 — Foundation

구현:

```text
FastAPI project
PostgreSQL
SQLAlchemy models
Alembic
Analysis CRUD
Issue CRUD
configuration
logging
```

완료 조건:

Analysis와 Issue를 생성하고 조회할 수 있다.

---

## Phase 2 — Initial Research

구현:

```text
LLM abstraction
Search abstraction
Query Generation
Search
Document Reader
Document Storage
```

완료 조건:

Issue 하나를 입력하면 관련 Query와 실제 Document가 DB에 저장된다.

---

## Phase 3 — Evidence Pipeline

구현:

```text
Fact Extraction
Fact Storage
Evidence Storage
Fact Verification
Knowledge Merge
```

완료 조건:

Document에서 추출된 Fact를 원문 Evidence까지 추적할 수 있다.

---

## Phase 4 — Iterative Research

구현:

```text
Gap Detection
Follow-up Query Generation
Research Iteration
Completeness Evaluation
Research Limits
```

완료 조건:

```text
Search
→ Fact
→ Gap
→ Re-search
```

루프가 실제 동작한다.

이 Phase가 프로젝트의 핵심 milestone이다.

---

## Phase 5 — Opinion Analysis

구현:

```text
Reaction Query
Public Search
Channel Classification
Aspect Extraction
Sentiment
Frame
Reason
```

완료 조건:

Public Content 하나에서 복수 Aspect를 구조화할 수 있다.

---

## Phase 6 — Keywords & Synthesis

구현:

```text
Keyword Extraction
Keyword Normalization
Positive Drivers
Negative Drivers
Implication Generation
Channel Strategy
```

---

## Phase 7 — Report

구현:

```text
Issue Report
Monthly Report
Markdown Renderer
HTML Renderer
Source Section
```

---

## Phase 8 — Dashboard

구현:

```text
Analysis List
New Analysis
Analysis Detail
Issue Detail
Research Monitor
Report View
```

---

# 76. Implementation Priority

Codex / Claude Code는 다음 우선순위를 따른다.

```text
P0

Database
→ API
→ Search
→ Document
→ Fact/Evidence
→ Research Loop
→ Opinion
→ Synthesis
→ Report

P1

Dashboard
→ Manual Review
→ DOCX

P2

PDF/PPT
→ Vector Search
→ Automation
→ Advanced Analytics
```

UI를 먼저 만드는 것보다 Research Pipeline을 우선한다.

---

# 77. Coding Rules for AI Coding Agents

Codex / Claude Code는 다음 규칙을 따른다.

### Rule 1

PRD에 없는 대규모 dependency나 infrastructure를 임의로 추가하지 않는다.

### Rule 2

기존 repository가 있다면 현재 architecture와 convention을 먼저 조사한다.

### Rule 3

큰 기능을 구현하기 전에 관련 기존 code, model, migration, API를 확인한다.

### Rule 4

LLM / Search provider를 business logic과 결합하지 않는다.

### Rule 5

LLM output은 가능한 한 Pydantic Structured Output을 사용한다.

### Rule 6

Fact와 Evidence의 연결을 깨뜨리는 구현을 하지 않는다.

### Rule 7

Fact Research와 Opinion Research를 데이터 모델과 service level에서 구분한다.

### Rule 8

검색 결과 snippet만으로 VERIFIED Fact를 만들지 않는다.

### Rule 9

근거가 없는 정보를 LLM이 생성하여 Research Gap을 채우게 하지 않는다.

### Rule 10

실패를 숨기지 않는다.

```text
FAILED
INCOMPLETE
CONFLICTED
```

상태를 명시적으로 표현한다.

### Rule 11

모든 외부 API credential은 환경변수로 관리한다.

### Rule 12

각 Phase 완료 후 test를 실행하고 실패를 해결한 뒤 다음 Phase로 진행한다.

---

# 78. Definition of Done

프로젝트의 핵심 MVP는 다음 흐름이 end-to-end로 동작할 때 완료된다.

```text
User-defined Issue
        ↓
Research Plan
        ↓
Query Generation
        ↓
Web Search
        ↓
Document Reading
        ↓
Fact Extraction
        ↓
Evidence Linking
        ↓
Knowledge Building
        ↓
Missing Information Detection
        ↓
Follow-up Search
        ↓
Verified Issue Knowledge
        ↓
Public Reaction Search
        ↓
Aspect / Sentiment / Frame / Reason
        ↓
Keyword Analysis
        ↓
Insight Generation
        ↓
Report Synthesis
        ↓
Evidence-grounded Report
```

가장 중요한 검증 조건:

> 최종 보고서의 주요 사실에서 시작해 Fact → Evidence → Document → Source URL까지 역추적할 수 있어야 한다.

---

# 79. Product Differentiation

이 프로젝트를 단순히 다음과 같이 구현하거나 설명하지 않는다.

```text
뉴스를 검색해서 LLM으로 요약하는 서비스
```

핵심 차별점은 다음 세 가지다.

### 1. Iterative Research

```text
Search
→ Knowledge
→ Gap Detection
→ Re-search
```

를 반복한다.

### 2. Evidence-grounded Knowledge

```text
Document
→ Evidence
→ Fact
→ Analysis
→ Report
```

lineage를 유지한다.

### 3. Fact / Opinion Separation

```text
Verified Fact Research
        +
Public Reaction Analysis
        ↓
Evidence-grounded Synthesis
```

구조를 사용한다.

---

# 80. Final Product Boundary

이 프로젝트의 MVP 경계를 다시 정의한다.

```text
INPUT

Region
Period
User-selected Issues

↓

PROCESS

Iterative Web Research
Evidence Verification
Opinion Analysis
Keyword Analysis
Insight Generation

↓

OUTPUT

Evidence-grounded
Issue / Monthly Analysis Report
```

AI는 분석할 이슈 자체를 결정하지 않는다.

AI의 역할은 사용자가 지정한 이슈를 **깊게 조사하고, 부족한 정보를 찾아 추가 조사하며, 사실과 공개 반응을 구분하여 분석하고, 근거가 추적 가능한 보고서로 만드는 것**이다.

이 원칙을 구현 전 과정에서 유지한다.
