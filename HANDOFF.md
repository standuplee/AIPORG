# AIPORG 공통 작업 인계

최종 정리: 2026-10-19. 작업 시작 시 실제 파일과 `git status`를 확인하고 사용자의 최신 요청을 우선한다. 이 문서는 현재 상태 요약이며, 과거 5~23차 상세 기록은 [구현 계획의 이관 기록](docs/superpowers/plans/2026-09-08-aiporg2-implementation.md#2026-10-19-인계-문서에서-이관한-상세-작업-기록)에 있다.

## 현재 목표와 구현 방향

월별 키워드로 온라인 여론을 수집·분석하고, 근거가 연결된 서술과 표·그림을 사용자가 UI에서 수정·승인한 뒤 동일 승인본에서 DOCX·Markdown·HWPX를 출력한다. 제작 기준은 [7월 월간 보고서 요구사항](docs/aiporg2/monthly-keyword-report-requirements.md)이다. 4개 이슈는 12쪽 기본 목표이며 이슈 수·장문에 따라 확장한다.

현재 개발 대상은 `app/` + `streamlit_app/console.py`다. `aiporg/`는 기존 1.0이며 출력 기능이 있다고 해서 2.0에 포팅된 것으로 보지 않는다.

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

전체 테스트 결과는 **395 passed**다.

## 이번 작업: 이슈 단위 감성·입장 분류 + 서술 이유 실데이터 채움

- 사용자 요청: 7월 참고 PDF의 "긍정/부정 여론 주요 원인" 화면을 보여주며, 이슈별 감성(긍정/부정/중립/혼재)과 입장(찬성/반대)이 어느 수준인지 질문 → 설계·구현까지 진행 승인.
- 코드 확인 결과 분류기가 전혀 없었고(`metadata["sentiment"]`를 쓰는 코드가 0줄), `IssueFinalizationService`가 모든 subissue를 고정 NEUTRAL로 채우고 있었다. 1.0(`aiporg/analyze/sentiment.py`, `aiporg/llm/sentiment_llm.py`)에 사전·LLM 하이브리드 분류기가 있었으나 2.0에 포팅되지 않았었고, "주요 원인"도 1.0 실제로는 polarity당 대표 문서 1개뿐이라 참고 PDF 수준(5~6개, 구체적 %)은 1.0도 자동 생성한 적이 없었음을 확인.
- 감성(일반 긍/부/중/혼재)과 입장(정책 찬/반)을 **서로 다른 두 축**으로 분리 설계(요구사항 §4.3). 신규 `StanceLabel` enum(`app/core/enums.py`), `IssueDetailSchema.stance` 필드 추가(기존 pinned contract test 갱신 포함), 신규 `app/sentiment/service.py::SentimentService`(사전 기반, 네트워크·LLM 없음)가 fact claim 텍스트에서 감성·입장을 각각 분류. `IssueFinalizationService`가 고정값 대신 이 분류 결과를 사용하도록 교체.
- 신규 `app/narrative/reasons.py`: `derive_narrative_reasons()`(이슈의 분류된 subissue에서 긍정/부정 요약을 최대 5개까지, 모자라면 있는 만큼만 추출 — 채우려고 생성 안 함), `aggregate_issue_sentiment()`(이슈 전체 대표 감성). `streamlit_app/console.py::page_narrative`의 `positive_reasons=[]/negative_reasons=[]/subissues[0].sentiment` 임시값을 전부 이걸로 교체. "4. 통계·이슈 검토" 표에 "세부 입장" 열 추가.
- 신규 마이그레이션 `20261019_000003`(issue_subissues에 stance 컬럼 추가, 빈 DB·실제 dev DB 양쪽에 적용 확인).
- 라이브 검증: 실제 fact 3건("일자리 확대…성과", "행정통합에 반대", "사업 지연…비판")을 실제 저장소 경로로 돌려 각각 POSITIVE/신규 OPPOSE(감성은 NEUTRAL — 반대 자체가 부정적 **감성** 단어는 아님을 확인)/NEGATIVE로 정확히 분류되고 `positive_reasons`/`negative_reasons`가 올바르게 채워지는 것을 확인.
- 신규 unit test 12개(SentimentService 6, narrative/reasons 5, IssueFinalizationService 실분류 1) + 기존 pinned contract 2개 갱신. `tests_v2`+`tests` **395 passed**(383 + 12).
- 다음 행동(결정 필요하면): 1.0의 LLM 배치 분류기 포팅 여부(사전 기반의 정확도 한계 보완), "주요 원인"을 fact 단위가 아니라 여러 근거를 묶은 요약으로 만들지 여부 — 둘 다 이번엔 범위 밖으로 남김.

## 기능 완료 시 커밋·푸시 규칙
- 기능 단위의 구현과 필요한 테스트가 완료되면 `HANDOFF.md`를 최신 상태로 갱신한 뒤 해당 기능의 변경만 선별하여 커밋하고 원격 브랜치에 푸시한다.
- 커밋 전 `git status`와 diff를 확인한다. 다른 작업자의 변경, 무관한 파일, 비밀값은 포함하지 않는다. 테스트가 실패하거나 기능이 미완성이면 완료 커밋으로 처리하지 않고 상태를 `HANDOFF.md`에 기록한다.
- 커밋 메시지는 `<type>(scope): <subject>` 형식을 사용한다. `scope`는 변경 영역을 나타내며 필요 없으면 생략할 수 있다. 제목은 변경 내용을 짧고 구체적으로 설명한다.
- 타입은 `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore` 중 변경 성격에 맞게 선택한다. 설명이 필요한 경우에만 본문을 쓰고, 관련 이슈가 있을 때만 푸터를 쓴다.
- 커밋 메시지에 `commit by Claude`, `Co-authored-by`, 도구 이름, 자동 생성 문구를 넣지 않는다. 변경 내용에 필요한 메시지만 작성한다.
- 푸시가 실패하면 강제 푸시하지 않는다. 실패 원인과 커밋 상태를 `HANDOFF.md`에 기록하고 충돌을 확인한다.
