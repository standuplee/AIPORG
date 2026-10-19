# Phase 5: 저장 데이터 기반 종합 분석

`app.analytics.service.AnalyticsService`는 기존 `AnalyticsSnapshotSchema.metrics`
내에 분석 결과를 저장한다. Pydantic 필드나 DB schema는 추가하지 않는다.

## 집계 기준

- `DocumentRepository.list_canonical(project_id)`가 반환하는 정제 완료 문서만 사용한다.
  같은 프로젝트의 `document_duplicates`에 포함된 문서는 조회에서 제외한다.
- 분석기간은 양 끝 날짜를 포함하며 기본 날짜 기준은 `Asia/Seoul`이다.
  발행일 없는 문서는 기간 집계에서 제외하고 `undated_document_ids`에 남긴다.
- 언급량은 문서 수다. 채널·출처·일별 집계마다 대응하는 문서 ID 목록을 저장한다.
  날짜별 0은 저장된 대상 문서가 없다는 뜻이며 실제 수집의 완전성을 보장하지 않는다.
- 감성은 기존 `CleanDocument.metadata["sentiment"]`의 유효한 enum 문자열만 집계한다.
  미지정·잘못된 값은 `unclassified`다. 별도 감성 분류 모델은 이번 단계에 포함하지
  않으며, 기존 Issue의 기본 neutral 값을 문서 감성으로 사용하지 않는다.
- 키워드는 제목과 본문을 합친 텍스트를 `kiwipiepy`로 형태소 분석해 일반·고유
  명사(NNG/NNP)만, 2글자 이상, casefold하여 세는 결정론적 빈도다(2026-10-19
  교체 — 문자 토큰 빈도만 셀 때 조사·동사·부사("있다"/"위해"/"지난"/"함께")와
  본문에 섞여 들어온 자바스크립트 토큰("var")까지 TOP10에 올라오는 것을 실데이터
  테스트로 확인해 명사 품사 필터로 바꿈). `kiwipiepy`를 쓸 수 없는 환경에서는
  숫자를 제외한 2글자 이상 문자 토큰 빈도로 자동 대체한다(`basis.keywords`에
  실제 사용한 방식이 기록됨). 중요도 순위(TF-IDF 등)는 아니며 여전히 빈도
  기준이다. `keyword_document_ids`로 각 빈도를 원문에서 재계산할 수 있다.
- 비교기간에 저장 문서가 있으면 문서 수 차이와 `(현재-이전)/이전*100`을 계산한다.
  기간 길이를 정규화하지 않은 관측 문서 수 비교다. 비교 문서가 없으면
  `no_comparison_documents`, 기간 자체가 없으면 `period_not_configured`이며
  비교 수치들은 `null`이다. 미수집을 0건 기준선으로 가정하지 않는다.
- 기존 Project contract는 비교기간을 필수로 요구한다. 서비스는 비교기간 없음도
  처리하지만 workflow에서는 기존 Project contract를 그대로 따른다.
- 이슈의 문서·출처·채널 수는 기존 issue/source_count 값을 복사하지 않고,
  VERIFIED/SUPPORTED Fact의 문서 참조와 분석기간 canonical 문서의 교집합에서
  다시 계산한다. UNCERTAIN/REJECTED Fact는 제외 목록에 남긴다.
- `basis`에는 계산 방법·기간·시간대와 정렬한 전체 입력의 SHA-256을 남긴다.
  기존 `run`에는 호출자가 전달한 run ID와 input/output version을 보존한다.
  이는 문서·Evidence 자체의 version lineage 보류 사항을 대체하지 않는다.

## 저장 및 상태 전이

`IssuesToAnalyticsWorkflow`는 `ISSUES_COMPLETED`에서만 실행된다. 모든 repository는
동일한 `session_scope`의 session으로 생성해야 한다. snapshot 저장 후 상태를
`ANALYTICS_COMPLETED`로 전진시키고, 외부 transaction이 둘을 함께 commit한다.
실패 시 transaction 전체가 rollback되어 마지막 성공 상태에서 재시도할 수 있다.

```python
from app.analytics.service import AnalyticsService
from app.db.session import create_session_factory, session_scope
from app.repositories.sqlalchemy import (
    SqlAlchemyAnalyticsRepository, SqlAlchemyDocumentRepository,
    SqlAlchemyFactRepository, SqlAlchemyIssueRepository, SqlAlchemyProjectRepository,
)
from app.workflows.issues_to_analytics import IssuesToAnalyticsWorkflow

# project_id: 이슈 확정이 완료된 기존 프로젝트 ID
# run: 호출자가 준비한 기존 VersionedRunSchema
factory = create_session_factory("sqlite:///aiporg2.db")
with session_scope(factory) as session:
    snapshot = IssuesToAnalyticsWorkflow(
        project_repository=SqlAlchemyProjectRepository(session),
        document_repository=SqlAlchemyDocumentRepository(session),
        fact_repository=SqlAlchemyFactRepository(session),
        issue_repository=SqlAlchemyIssueRepository(session),
        analytics_repository=SqlAlchemyAnalyticsRepository(session),
        analytics_service=AnalyticsService(),
    ).run(project_id, run)
```

## 검증

```bash
uv run --with-requirements requirements-dev.txt python -m pytest tests_v2 tests -q
```

통합 테스트는 외부 네트워크 없이 Alembic으로 생성한 SQLite DB에서 실행하며,
외래키 검사를 활성화한다. Evidence → Fact → Issue → Analytics,
snapshot 재조회, 중복 문서 제외, 상태 전이 실패 시 rollback과 재시도를 검증한다.
