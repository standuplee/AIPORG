# AIPORG

**AI Public Opinion Report Generator** — 월별 키워드로 온라인 여론을 수집하고, 근거가 연결된 분석과 서술을 사람이 검수하여 보고서로 만드는 프로젝트입니다.

현재 개발 중심은 **AIPORG 2.0 (`app/`)과 로컬 Streamlit UI**입니다. 기존 1.0 (`aiporg/`)은 별도로 유지합니다. 2.0은 수집부터 서술·시각자료 승인과 HWPX 시제품 다운로드까지 연결되어 있으며, 전체 월간 보고서와 DOCX·Markdown 출력은 개발 중입니다.

## 빠른 시작 — Streamlit UI

저장소 루트에서 실행합니다. 개발·검증 환경은 **Python 3.12**입니다.

```bash
# 최초 설치
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements-dev.txt

# 최초 설정: 이미 .env가 있다면 복사하지 말고 기존 파일을 수정합니다.
cp .env.example .env
```

`.env`에 사용할 수집 채널의 `AIPORG2_` 환경변수를 채운 뒤 실행합니다.

```bash
# Streamlit UI 실행
./.venv/bin/streamlit run streamlit_app/console.py --server.address 127.0.0.1
```

브라우저에서 **http://127.0.0.1:8501**에 접속합니다. 종료는 터미널에서 `Ctrl+C`입니다.

앱 시작 시 Alembic 마이그레이션을 적용하며, 기본 DB는 저장소 루트의 `aiporg2.db`입니다. 기존 DB를 사용하는 경우 업그레이드 전 백업합니다. `.env`는 UI가 자동으로 읽지만, 값을 바꾼 뒤에는 Streamlit 프로세스를 재시작해야 합니다.

### 환경변수

| 용도 | 2.0 환경변수 |
| --- | --- |
| 네이버 뉴스·댓글 / 커뮤니티 URL 검색 | `AIPORG2_NAVER_CLIENT_ID`, `AIPORG2_NAVER_CLIENT_SECRET` |
| 다음 검색 | `AIPORG2_KAKAO_REST_API_KEY` |
| 유튜브 영상·댓글 | `AIPORG2_YOUTUBE_API_KEY` |
| 구글 Custom Search | `AIPORG2_GOOGLE_API_KEY`, `AIPORG2_GOOGLE_SEARCH_ENGINE_ID` |
| Gemini 서술 초안 | `AIPORG2_GEMINI_API_KEY` |
| DB 변경(선택) | `AIPORG2_DATABASE_URL` — 기본 `sqlite:///aiporg2.db` |

인증정보가 없는 수집기는 UI에서 사용할 수 없습니다. Gemini 키가 없거나 호출에 실패하면 UI는 결정론적 템플릿으로 초안을 생성합니다. 현재 어댑터의 기본 모델 설정은 `gemini-2.5-flash`입니다. GPT·Claude 어댑터는 2.0에 아직 구현하지 않았습니다.

1.0의 접두사 없는 키와 2.0의 `AIPORG2_` 키는 별개입니다. 전체 설정 예시는 [.env.example](.env.example)을 참고하고 실제 키는 커밋하지 않습니다.

## 사용 흐름

1. **월별 프로젝트**: 프로젝트와 분석·비교기간을 설정합니다.
2. **수집 설정·실행**: 그달의 키워드 목록과 채널을 선택합니다. 지역·기관·인물 정보를 고정 검색어로 자동 추가하지 않습니다.
3. **수집 결과 검토**: 실행 이력과 수집 문서를 확인합니다.
4. **통계·이슈 검토**: 이슈 확정과 통계 집계를 실행합니다.
5. **서술 편집**: 이슈를 선택해 초안을 생성하고, 근거를 확인하면서 문장 수정·버전 비교·승인을 진행합니다.
6. **시각 자료 편집·승인**: 채널 비중과 TOP10 키워드 자료를 생성하고 표시 항목을 편집·승인합니다.
7. **보고서 미리보기**: 서술과 필수 시각자료의 승인 상태를 확인하고 최종 승인합니다.
8. **출력·이력**: 표지·목차·요약으로 구성된 HWPX 시제품을 다운로드합니다.

같은 프로젝트의 수집은 한 번만 실행할 수 있습니다. 키워드를 바꾸어 다시 수집하려면 새 프로젝트를 만듭니다. 서술 버전은 현재 **프로젝트 단위**로 저장되므로, 다른 이슈로 초안을 생성하면 프로젝트의 새 서술 버전이 됩니다.

## 현재 구현 범위

| 영역 | 구현 상태와 범위 |
| --- | --- |
| 수집 | 네이버·다음·유튜브·구글·커뮤니티, 키워드×채널 배치 수집 |
| 댓글 | 네이버·유튜브 지원. 본문 언급량과 댓글 건수 분리 집계 |
| 정제·근거 | 기사 본문 추출, 인코딩 처리, 중복 제거, Evidence → Fact → Issue 연결 |
| 이슈 구성 | 근거 문서의 수집 키워드 기준으로 그룹화 |
| 분석 | 고유 문서 수, 채널·출처·일별 집계, 키워드 빈도, 기존 감성 라벨·비교기간 집계 |
| 서술 | Gemini/템플릿 초안, 근거 검증, 수정·버전 비교·승인 |
| 시각자료 | VIS-02 채널 비중, VIS-07 TOP10 키워드의 편집·버전 저장·개별 승인 |
| 출력 | `python-hwpx` 기반 표지·목차·요약 시제품. 전체 보고서·DOCX·Markdown은 미구현 |

커뮤니티는 클리앙·디시인사이드·펨코·루리웹·더쿠를 지원하며, 현재 [설정 파일](config/community.yaml)에는 다섯 사이트가 활성화되어 있습니다. 실제 수집은 사이트별 허용 경로·요청 제한·robots.txt와 접근 가능 여부에 따릅니다. 활성화가 수집 성공을 보장하지는 않습니다. 2.0 블로그 수집기는 아직 없으며 X·인스타그램은 현재 범위에서 제외합니다.

### 분석·출력의 한계

- 언급량은 수집 후 중복을 제거한 문서 수입니다. 전체 온라인 여론의 전수 수치나 표본조사 결과가 아닙니다.
- 감성은 저장된 라벨을 집계합니다. 별도 감성 분류 모델은 연결하지 않았으며 라벨이 없으면 미분류입니다.
- TOP10은 형태소 분석과 붙어 있는 명사류 구절 병합에 따른 **빈도 순위**입니다. 중요도 평가, 동시출현 짝짓기(`폭염·열대야`), 카테고리 분류는 구현하지 않았습니다. 형태소 분석기를 사용할 수 없으면 문자 토큰 방식으로 대체하고 집계 기준에 기록합니다.
- 비교기간 데이터가 없으면 증감률을 만들지 않습니다. 구글 검색 결과의 원문 채널은 현재 `NEWS`로 단순화되어 있습니다.
- 최종 승인 게이트는 있지만 **승인 당시 버전을 고정한 출력 번들은 아직 미완성**입니다. 현재 출력 화면은 최신 서술·시각자료를 읽으므로 최종 승인 후 수정한 버전의 재승인 여부를 출력 단계에서 완전히 보장하지 못합니다.
- HWPX는 3쪽 구성을 목표로 한 시제품입니다. 실제 한컴에서 열림·쪽수·줄바꿈·표 넘침은 아직 검증하지 않았습니다.

자세한 산식과 근거 추적 방식은 [분석 기준](docs/aiporg2/analytics.md)을 참고합니다.

## 구현 방향

목표는 매월 달라지는 키워드에 대해 수집부터 검수·출력까지 한 UI에서 처리하는 것입니다. [7월 기준 월간 보고서 요구사항](docs/aiporg2/monthly-keyword-report-requirements.md)을 제작 기준으로 삼으며, 4개 이슈는 12쪽을 기본 목표로 하고 이슈 수·본문 길이에 따라 확장합니다. 참고본의 수치나 문구를 실제 분석 결과처럼 복사하지 않습니다.

```text
월별 키워드 → 수집 → 정제·중복 제거 → Evidence / Fact / Issue
           → AnalyticsSnapshot → LLM 서술 초안·근거 검증
           → 서술·표·그림의 사용자 수정·개별 승인
           → 승인 버전 고정 → 동일 본문의 DOCX / Markdown / HWPX
```

다음 구현의 핵심은 승인된 서술·통계·시각자료·템플릿 버전을 함께 고정하는 출력 계약, 나머지 표·그림 편집, 전체 HWPX 조립, 동일 승인본의 DOCX·Markdown 출력입니다. 승인 후 변경에는 재승인이 필요하도록 완성해야 합니다. 원본 HWPX·표지 자산 확보와 실제 한컴 검증도 남아 있습니다.

HWPX 보고서 구성과 서식은 AIPORG의 Report/Writer 계층에서 담당합니다. 현재 `python-hwpx==6.8.0`을 사용하며, 포맷 라이브러리 자체의 수정이 필요해지면 별도 fork로 관리합니다.

## 저장소 구조

```text
app/                 AIPORG 2.0
  collectors/        외부 수집·본문 추출
  cleaning/, dedup/  정제·중복 제거
  evidence/, facts/, issues/  근거·사실 검증·이슈 구성
  analytics/         저장 데이터 집계
  narrative/         템플릿·LLM 서술 및 검증
  visualization/     시각자료 구성
  report/            최종 승인·HWPX 시제품
  models/, schemas/  DB 모델·Pydantic 계약
  repositories/      DB 접근
  workflows/         단계별 실행
streamlit_app/       로컬 검수 UI
alembic_v2/          2.0 DB 마이그레이션
config/             수집 정책 및 1.0 실행 설정
tests_v2/          2.0 unit·contract·integration 테스트
tests/             1.0 회귀 테스트
aiporg/             기존 1.0 CLI·분석·보고서 구현
docs/               요구사항·설계·구현 기록
```

## 개발·검증

```bash
# 2.0과 기존 1.0 회귀 테스트
./.venv/bin/python -m pytest tests_v2 tests -q

# 2.0 통합 테스트만 실행
./.venv/bin/python -m pytest tests_v2/integration -q
```

[AGENTS.md](AGENTS.md)의 규칙을 따릅니다. 임의 schema 추가와 기존 Pydantic 모델 이름 변경을 금지하며, DB 쓰기는 Repository를 통합니다. Collector는 LLM을 호출하지 않고 Analyzer는 웹 요청을 하지 않습니다. Writer는 새 사실을 만들지 않으며 근거 없는 수치를 생성하지 않습니다. 모듈 변경에는 unit test를 작성하고 integration test 실패 시 다음 기능으로 넘어가지 않습니다.

작업 시작 시 `git status`와 [HANDOFF.md](HANDOFF.md)를 확인합니다. 인계 문서는 현재 상태를 요약하고, 상세 이력은 [구현 계획·진행 기록](docs/superpowers/plans/2026-09-08-aiporg2-implementation.md)에 유지합니다.

## 기존 1.0 실행

아래 명령은 **2.0 UI와 별개인 기존 CLI**입니다. 1.0의 YAML 설정·환경변수·출력 형식을 사용하며 2.0 승인 흐름을 거치지 않습니다.

```bash
./.venv/bin/python -m aiporg.cli run \
  --config config/chungnam_202606.yaml \
  --formats docx,html,md,json \
  --out output
```

설정에 `data_fixture`가 있으면 저장된 예제 분석 결과를 사용합니다. 예제 결과를 새로 수집한 월간 실데이터로 취급하지 않습니다.

## 관련 문서

- [현재 상태와 다음 행동](HANDOFF.md)
- [새 Issue Research & Analysis Engine 설계](docs/superpowers/specs/2026-10-23-issuescope-engine-design.md)
- [새 PRD 구현 계획](docs/superpowers/plans/2026-10-23-issuescope-engine.md)
- [월간 키워드 보고서 요구사항·인수 조건](docs/aiporg2/monthly-keyword-report-requirements.md)
- [서술 계약](docs/aiporg2/narrative-design.md)
- [시각자료·보고서 승인 계약](docs/aiporg2/visualization-design.md)
- [분석 산식·집계 기준](docs/aiporg2/analytics.md)
- [전체 구현 계획·상세 작업 기록](docs/superpowers/plans/2026-09-08-aiporg2-implementation.md)
