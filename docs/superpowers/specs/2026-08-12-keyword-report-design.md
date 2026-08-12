# Keyword Report Design

## Goal

기존 AIPORG의 수집 원천과 기존 보고서 생성 기능은 유지하면서, 동일한 `Document`
입력을 기반으로 레퍼런스 문서
`2026년도 7월 충남 온라인여론 키워드조사 분석 보고서` 형식을 재현하는 신규 보고서
타입을 추가한다.

이 신규 타입은 기존 보고서와 별도의 데이터 모델, 분석 파이프라인, DOCX 렌더링 경로를
가져야 하며, 기존 `run` 흐름에 선택 가능한 report profile 로 통합되어야 한다.

## Context

- 현재 AIPORG는 뉴스, X, 인스타그램, 유튜브, 커뮤니티, 블로그, RSS 등에서 수집한
  `Document`를 기반으로 기존 공공기관형 월간 여론분석 보고서를 생성한다.
- 기존 리포트는 `AnalysisResult`, `ReportModel`, `TemplateNarrator`, 기존
  `report/*_writer.py` 조합을 전제로 한다.
- 새 레퍼런스 문서는 같은 주제 영역이지만, 구성과 산출물 성격이 다르다.
  - 표지, 목차, 리포트 서머리 페이지가 별도로 존재함
  - 본문이 "핵심 이슈 4건", "채널별 동향", "키워드 TOP 20", "감성 원인",
    "운영 제언", "출처/방법론" 중심으로 구성됨
  - 기존 보고서보다 브리핑형, 키워드형, 운영 제언형 문서에 가깝다

## Non-Goals

- 기존 보고서 포맷이나 출력 구조를 변경하지 않는다.
- 기존 `AnalysisResult`에 조건문을 누적해 두 포맷을 동시에 억지로 수용하지 않는다.
- 1차 범위에서 HTML/Markdown 출력의 완전한 레퍼런스 재현을 목표로 하지 않는다.
- 레퍼런스 PDF의 픽셀 단위 복제는 목표가 아니다.
- 새 보고서 때문에 새로운 수집기를 대거 도입하지 않는다.

## Reference Structure

HWP preview text 기준으로 신규 보고서의 필수 섹션 구조는 아래와 같다.

1. 표지
2. 목차
3. `REPORT SUMMARY`
4. `제1장 분석 개요`
   - 1.1 분석 목적
   - 1.2 분석 개요
   - 1.3 분석 범위 및 주제어 체계
5. `제2장 월간 주요 이슈 동향`
   - 이슈 4건
6. `제3장 온라인 채널별 여론 동향`
   - 3.1 채널별 언급량 분포
   - 3.2 월간 주요 키워드 TOP 20
7. `제4장 감성 분석 - 긍·부정 여론 동향`
   - 4.1 전반 감성 분포
   - 4.2 긍정 여론 주요 원인
   - 4.3 부정 여론 주요 원인
8. `제5장 시사점 및 도정 운영 제언`
   - 5.1 핵심 시사점
   - 5.2 채널별 대응 전략 제언
9. `제6장 출처 및 참고자료`
   - 6.1 여론조사 출처
   - 6.2 뉴스 및 언론 출처
   - 6.3 참고 분석 방법론

## Product Requirements

### User-facing behavior

- 사용자는 기존과 동일하게 YAML 설정과 실행 명령을 사용하되, 신규 보고서 타입을 선택할
  수 있어야 한다.
- 기존 보고서 생성 명령은 그대로 동작해야 한다.
- 신규 보고서 생성 시 최소 `DOCX` 결과물을 생성해야 한다.
- 신규 DOCX는 레퍼런스 문서와 섹션 구조, 문체 톤, 정보 배치 의도를 충실히 반영해야 한다.

### Functional requirements

신규 보고서 전용 결과 모델은 최소 아래 정보를 포함해야 한다.

1. 보고서 메타 요약
   - 분석기간
   - 분석채널 수
   - 핵심 검색어
   - 전체 긍정여론 비율
   - 전월 대비 증감
2. 핵심 이슈 4건
   - 이슈명
   - 요약 설명
   - 대표 근거 문장 또는 설명
   - 대표 출처
   - 요약 코멘트
3. 채널별 동향
   - 채널명
   - 언급량 또는 비중
   - 전월 대비 방향성
   - 대표 키워드
4. 월간 키워드 TOP 20
   - 순위
   - 키워드
   - 카테고리
5. 감성 분석
   - 긍정/부정/중립 분포
   - 긍정 원인 항목
   - 부정 원인 항목
6. 운영 제언
   - 핵심 시사점
   - 채널별 대응 전략
7. 출처/방법론
   - 출처 목록
   - 분석 도구 설명
   - 방법론 설명

### Comparison-period contract

- 신규 `keyword` 보고서는 항상 비교기간 데이터를 함께 계산한다.
- 비교기간은 기본적으로 `분석 대상 월의 직전 1개월`로 고정한다.
  - 예: 2026년 7월 보고서이면 비교기간은 2026년 6월 1일~6월 30일
- 비교기간 수집 원천과 전처리 규칙은 본 기간과 동일해야 한다.
- 비교기간 데이터는 아래 계산에 필수 사용된다.
  - summary 의 `전월 대비 증감`
  - 채널별 `전월 대비 방향성`
  - 필요 시 이슈 급증 판단
- 비교기간 데이터가 완전히 비어 있거나 수집 실패한 경우 보고서 생성은 허용하되,
  해당 필드는 숫자 대신 명시적 상태값 `비교 불가`로 표시한다.
  이 상태는 정상 케이스가 아니라 fallback 으로 취급한다.

### Data source requirements

- 수집 원천은 기존과 동일한 `Document` 기반 파이프라인을 우선 사용한다.
- 추가 데이터가 필요할 경우 확장 가능하되, 기본 설계는 기존 수집층 재사용을 전제로 한다.
- 레퍼런스 수치나 문장을 하드코딩으로 복제하지 않는다.
- 동일 입력에서 재현 가능한 분석 결과를 우선한다.

### Keyword collection contract

- 신규 `keyword` 보고서는 두 층의 수집 키워드를 사용한다.
  - 기본 키워드 레이어: 기존 광범위 수집 키워드
  - 추가 이슈 키워드 레이어: 월간 핵심 이슈를 더 잘 포착하기 위한 보조 키워드 묶음
- 기본 키워드 레이어는 기존 설정의 기관/인물 중심 키워드를 그대로 사용한다.
  - 예: `충청남도`, `충남도정`, `충남도지사`, `박수현` 및 그 확장어
- 추가 이슈 키워드 레이어는 코드 내장값이 아니라 YAML 설정 파일에서 직접 정의한다.
- 추가 이슈 키워드는 긴 문장 전체를 단일 검색어로 두기보다,
  실제 기사/SNS 표현에 잘 걸리는 짧은 핵심어 묶음으로 분해해 저장한다.
- 추가 이슈 키워드는 수집 대상을 완전히 제한하는 필터가 아니라,
  아래 목적의 보조 신호로 사용한다.
  - 이슈 랭킹 가중치
  - 대표 키워드 보강
  - 감성 원인 후보 보강

권장 YAML 예시는 아래와 같다.

```yaml
keywords:
  충청남도:
    - 충남
    - 충남도
    - 충남도정
    - 충남도청
    - 충청남도청
    - 충남도의회
    - 충청남도의회
    - 충남지사
    - 충남도지사
    - 충청남도지사
    - 박수현

keyword_report:
  issue_keywords:
    충효예 충청정신:
      - 충효예
      - 충청정신
      - 충효예 충청정신
      - 박수현 충효예
    AI수도 충남:
      - 대한민국 AI수도 충남
      - AI수도 충남
      - 충남 AI
      - 3력 혁신
      - 전력 수력 인력
    발전통합 본사 유치:
      - 발전통합
      - 발전통합 본사
      - 본사 유치
      - 충남 유치
    폭염 기후재난:
      - 기후살인
      - 폭염
      - 기후재난
      - 폭염 대책
      - 취약계층 보호
```

- 구현 시 `keyword_report.issue_keywords` 가 비어 있어도 보고서는 생성 가능해야 한다.
- 다만 해당 필드가 존재하면 신규 `keyword` 보고서 분석기는 이를 우선적으로 반영해야 한다.

## Recommended Architecture

권장안은 `기존 수집 공유 + 신규 report profile` 이다.

### New modules

- `aiporg/models_keyword_report.py`
  - 신규 보고서 전용 데이터 모델
- `aiporg/analyze_keyword_report/`
  - 신규 보고서용 분석 오케스트레이터와 세부 분석기
- `aiporg/report/keyword_docx_writer.py`
  - 신규 보고서 전용 DOCX writer
- `aiporg/report/keyword_layout.py`
  - 표지, 목차, summary card, 표 스타일, 장 제목 스타일 등 레이아웃 구성
- `aiporg/report/keyword_sections.py`
  - 장별 렌더링 헬퍼

### Existing modules to extend

- `aiporg/cli.py`
  - 기존 `run` 명령에 보고서 타입 선택 인자 추가
- `aiporg/config.py`
  - 보고서 타입 또는 프로필 선택을 위한 설정 필드 추가 가능
- `aiporg/charts/`
  - 기존 차트 재사용 가능 여부를 검토하고, 신규 보고서용 차트를 별도 추가 가능

### Integration contract

- `aiporg.cli.run` 은 보고서 타입에 따라 명시적으로 두 경로 중 하나를 선택한다.
  - `default` 또는 미지정: 기존 `AnalysisResult -> ReportModel -> narrator -> existing writer`
  - `keyword`: `KeywordAnalysisPipeline -> KeywordReportModel -> keyword writer`
- 신규 `keyword` 경로는 기존 `Narrator` 계층을 기본적으로 사용하지 않는다.
  - 이유: 레퍼런스 문서는 자유 서술보다 규칙 기반 브리핑 문서에 가깝기 때문
  - 단, 일부 요약 문장 보강용 선택적 helper 로만 사용 가능
- 차트 생성도 profile 별로 분기한다.
  - 기존 `ChartRenderer.render_all(...)` 을 그대로 재사용하지 않고,
    `keyword` 전용 renderer 또는 profile-aware renderer 를 둔다.
- 설정 검증 단계에서 `report_type=keyword` 이면 profile 전용 필수 조건을 검증한다.
  - 최소 `formats` 제약
  - 비교기간 계산 가능 여부
  - keyword writer 에 필요한 메타 값 존재 여부

### Output-format contract

- `report_type=keyword` 의 1차 지원 포맷은 `docx` 만 허용한다.
- 사용자가 `html`, `md`, `json` 을 요청하면 조용히 무시하지 않고 명시적으로 실패시킨다.
- 실패 메시지는 `keyword report currently supports only docx` 수준으로 분명해야 한다.
- 기존 보고서 타입은 기존 포맷 동작을 그대로 유지한다.

## Data Model Design

신규 모델은 기존 `AnalysisResult`와 별개여야 한다. 대표 예시는 아래와 같다.

- `KeywordReportModel`
  - `meta`
  - `summary`
  - `issues`
  - `channel_overview`
  - `top_keywords`
  - `sentiment_overview`
  - `positive_drivers`
  - `negative_drivers`
  - `implications`
  - `channel_recommendations`
  - `sources`
  - `methodology`

- `KeywordReportSummary`
  - 분석기간
  - 분석채널 수
  - 핵심 검색어
  - 긍정여론
  - 전월대비 증감

- `KeywordIssue`
  - rank
  - title
  - subtitle
  - body
  - evidence
  - source_notes
  - comparison_delta
  - representative_documents

- `ChannelTrendItem`
  - channel
  - share_or_volume
  - change_direction
  - change_pct
  - keywords

- `RankedKeywordItem`
  - rank
  - keyword
  - category

- `SentimentDriver`
  - sentiment
  - title
  - detail
  - evidence

- `SourceReference`
  - source_id
  - title
  - url
  - publisher
  - published_at
  - channel

### Evidence contract

- 신규 보고서의 모든 핵심 서술 항목은 하나 이상의 `Document` 근거를 가져야 한다.
- 최소 대상:
  - 핵심 이슈 4건
  - 긍정/부정 원인 항목
  - 시사점/제언 항목
- `representative_documents` 는 내부적으로 `doc_id` 목록을 유지하고,
  렌더링 시에는 사람이 읽을 수 있는 출처 텍스트로 변환한다.
- 출처 목록은 URL 중복 제거 후 `publisher`, `published_at`, `title` 기준으로 정렬 규칙을 갖는다.
- 동일 기사 재배포 문서는 dedup 이후 하나의 대표 출처만 남긴다.
- 생성 문장은 근거 문서와 수치적으로 모순되면 안 된다.

## Analysis Pipeline Design

### Pipeline entry

- 입력은 기존과 동일하게 `Document` 목록과 `ReportMeta` 계열 설정을 받는다.
- 출력은 신규 `KeywordReportModel` 이다.

### Analysis stages

1. 이슈 선정
   - 문서 군집
   - 기간 내 급증 키워드 탐지
   - 문서 반응도 또는 중요도 가중치 적용
   - 최종 4개 이슈 선별
   - 권장 점수식 예시:
     - `issue_score = cluster_volume * 0.5 + growth_score * 0.25 + source_weight * 0.15 + engagement_score * 0.10`
   - tie-breaker:
     - 1순위 `growth_score`
     - 2순위 대표 출처 신뢰도
     - 3순위 대표 문서 발행시각 최신순

2. 채널별 동향 산출
   - 채널별 문서량 집계
   - 반드시 전월 비교용 이전 기간 집계
   - 채널별 대표 키워드 추출

3. 월간 키워드 TOP 20
   - 연관 키워드 추출
   - 중복/불용어 정리
   - 카테고리 규칙 분류
   - 동점 시 빈도 우선, 이후 확산 채널 수 우선

4. 감성 동향
   - 전체 감성 분포 집계
   - 긍정/부정 문서 그룹 분리
   - 원인성 키워드와 대표 근거 문장 추출

5. 운영 제언
   - 규칙 기반 초안 생성
   - 기본은 LLM 없이 재현 가능해야 한다
   - 필요 시 LLM 보강 가능
   - 단, LLM 보강은 비결정적 부가 기능이며 기본 acceptance 에 포함되지 않는다

6. 출처 및 방법론
   - 사용 문서 출처 목록 정리
   - 사용 분석 기법 텍스트화

### Classification ownership

- 키워드 카테고리 분류 규칙과 불용어 사전은 코드에 명시된 사전 파일로 관리한다.
- 이슈/키워드 분류가 모델 호출에만 의존해서는 안 된다.
- 규칙 사전 변경은 테스트 fixture 갱신과 함께 관리한다.

## Rendering Requirements

### Output priority

- 1차 목표는 `DOCX`
- 이후 필요 시 HTML/MD는 확장

### Rendering behavior

- 레퍼런스 문서와 같은 장/절 구조를 유지한다.
- 표지, 목차, summary 페이지를 별도 렌더링한다.
- 요약 카드, 표, 리스트, 인용 출처 영역을 장별로 분리한다.
- 데이터가 부족한 경우 문서가 깨지지 않도록 축약 문구와 빈 상태 렌더링 규칙을 둔다.
- 숫자는 실제 산출값을 사용하고, 설명문은 그 숫자와 모순되지 않아야 한다.

### Layout invariants

- 목차는 필드 기반 자동 TOC 가 아니라 정적 렌더링으로 구현한다.
  - 이유: 테스트 가능성과 레퍼런스 정합성 확보
- `REPORT SUMMARY` 페이지는 최소 아래 요소를 포함해야 한다.
  - 분석기간
  - 분석채널 수
  - 핵심 검색어
  - 긍정여론
  - 전월 대비 증감
  - 핵심 이슈 4건 요약
  - 핵심 제언 3~4건
- 차트는 장식이 아니라 정보 요소로 취급한다.
  - 섹션별 필수/선택 차트를 명시적으로 정의해야 한다.
  - 필수 차트가 생성 실패하면 표나 텍스트 요약으로 대체해야 한다.
- sparse data 상황에서도 아래는 항상 유지된다.
  - 표지
  - 목차
  - summary 페이지
  - 제1~6장 제목
  - 빈 상태 설명문

### Section-level minimum content

- 제2장: 이슈는 최대 4건, 부족하면 실제 건수만 렌더링
- 제3장: 채널 표는 최소 1개 행 이상, 없으면 "수집 결과 없음" 행 렌더링
- 제4장: 감성 차트 또는 동등한 표 1개 이상
- 제6장: 출처 목록과 방법론 설명은 항상 존재

### Style requirements

- 공공기관 보고서형 분석체를 유지한다.
- 개조식 서술과 짧은 분석 문장을 우선한다.
- 지나친 자유 생성보다 템플릿 일관성을 우선한다.

## CLI and Configuration

### CLI changes

기존 `run` 흐름은 유지하고, 신규 옵션으로 분기한다.

예시:

```bash
python -m aiporg.cli run \
  --config config/chungnam_202606.yaml \
  --report-type keyword \
  --formats docx \
  --out output_keyword
```

`--report-type keyword` 와 함께 `--formats` 가 생략되면 내부 기본값은 `docx` 로 강제한다.

### Config changes

선택지는 두 가지다.

1. CLI 인자로만 보고서 타입 지정
2. YAML에 `report_type` 필드 추가

권장안은 CLI 인자 우선, YAML 보조 허용이다. 기존 설정 파일 호환성을 유지하기 쉽다.
다만 1차 구현에서는 YAML의 `report_type` 보다 CLI 값을 우선한다.

신규 `keyword` 보고서를 위해 YAML에는 아래 확장 필드를 추가할 수 있다.

- `keyword_report.issue_keywords`
  - `이슈명 -> 실제 수집 보조 키워드 목록` 매핑
  - 작성 주체는 사용자
  - 기본값은 빈 매핑 허용

`issue_keywords` 는 기존 `keywords` 를 대체하지 않고 보완한다.

## Testing Strategy

### Unit tests

- 신규 데이터 모델 직렬화/복원 테스트
- 이슈 선정 로직 테스트
- 채널별 동향 계산 테스트
- 키워드 카테고리 분류 테스트
- 감성 원인 추출 테스트

### Integration tests

- fixture 기반 신규 보고서 모델 생성 테스트
- 신규 DOCX writer 산출 테스트
- 기존 보고서 생성 경로 회귀 테스트

### DOCX verification method

- 테스트는 최소 아래를 검증해야 한다.
  - DOCX 내부 XML 또는 문단 추출 기준 장 제목 순서
  - 목차/summary/제1~6장 존재 여부
  - 필수 표 또는 차트 대체 요소 존재 여부
  - sparse data fixture 에서도 렌더링 성공 여부
- 시각 정합성이 중요한 표본 문서는 golden fixture DOCX 또는 렌더링된 텍스트 구조 비교로 검증한다.
- acceptance 단계에서는 대표 샘플 DOCX를 수동 검토해 레퍼런스와 구조 대응을 확인한다.

### Regression protection

- 기존 `run` 기본 동작이 변하지 않는지 검증
- 신규 옵션 미사용 시 기존 산출물이 동일한지 확인

## Failure Handling

- 수집 문서가 적을 때 이슈 수를 축소할 수 있어야 한다.
- 전월 비교 데이터가 없을 경우 증감 항목은 `비교 데이터 없음` 등 안전 문구로 대체한다.
- 특정 채널 데이터가 없을 경우 해당 채널을 제외하거나 0건으로 표기한다.
- 감성 원인이 충분히 분리되지 않을 경우 대표 키워드 기반 요약으로 폴백한다.

## Acceptance Criteria

1. 기존 보고서 생성 기능이 그대로 유지된다.
2. 신규 보고서 타입을 선택해 별도 DOCX를 생성할 수 있다.
3. 신규 DOCX는 레퍼런스 문서와 동일한 섹션 순서와 의미 구조를 가진다.
4. 신규 결과 모델과 분석 파이프라인은 기존 `AnalysisResult` 경로와 분리되어 있다.
5. 신규 기능 추가 후 기존 테스트가 깨지지 않는다.
6. 데이터 부족 상황에서도 문서 렌더링이 실패하지 않는다.
7. `report_type=keyword` 에서 `docx` 이외 포맷 요청 시 명시적으로 실패한다.
8. summary 와 채널 동향의 전월 비교 필드는 실제 비교기간 데이터 또는 `비교 불가` 상태로만 표현된다.

## Open Questions

- 레퍼런스 문서의 차트 구성과 시각 스타일을 어느 수준까지 정확히 맞출지 결정 필요

## Recommendation

구현은 `Document` 수집층을 공유하고, 신규 분석 모델과 DOCX writer 를 분리하는 방향으로
진행한다. 이 방식이 기존 기능 회귀 위험을 가장 낮추면서도, 레퍼런스 문서에 가까운
구조적 재현을 가능하게 한다.
