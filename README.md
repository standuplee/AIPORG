# AIPORG — AI Public Opinion Report Generator

> AIPORG 2.0은 별도 `app/` 경로에서 개발 중이며 현재 이슈 확정 후 종합 분석
> (`ANALYTICS_COMPLETED`)까지 연결되어 있다.
> [2.0 구현 진행 기록](docs/superpowers/plans/2026-09-08-aiporg2-implementation.md)과
> [분석 실행·집계 기준](docs/aiporg2/analytics.md)을 참고한다.
> 아래 CLI와 보고서 생성 설명은 기존 1.0 기준이다.

온라인 여론 데이터를 자동 수집·분석하여 **공공기관 수준의 월간 여론분석 보고서**를
자동 생성하는 시스템. 사용자는 `프로젝트명 / 분석기간 / 키워드 / 보고서 제목`만
입력하면 원본 리포트(예: 충남 202603 여론분석 리포트)와 동일한 구성의
보고서를 DOCX/HTML/Markdown 으로 출력한다.

```
Crawler ──▶ AI 분석 파이프라인 ──▶ 공공기관 문체 서술(LLM) ──▶ 자동 보고서
                                                              (DOCX/HTML/MD)
```

## 빠른 시작

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# 분석 결과 fixture 재생성(선택)
./.venv/bin/python -m scripts.build_chungnam_fixture

# 보고서 생성 (충남 2026-06, 도지사 = 박수현)
./.venv/bin/python -m aiporg.cli run \
    --config config/chungnam_202606.yaml \
    --formats docx,html,md,json \
    --out output
```

생성물은 `output/` 디렉터리에 저장된다.

## 입력 설정 (사용자가 편집하는 유일한 파일)

`config/chungnam_202606.yaml` — 프로젝트명, 분석대상(지자체/직위/인물),
분석기간, 키워드 수집 체계, 수집 채널, LLM provider 를 지정한다.
다른 지자체·기업·인물로 확장하려면 이 파일만 복제·수정하면 된다.

## 아키텍처

```
aiporg/
├─ config.py          입력 설정 로더/검증 (RunConfig, ReportMeta)
├─ models.py          공유 데이터 모델 (Document, AnalysisResult, ReportModel ...)
├─ collect/           수집 계층 (PRD 5) — 뉴스/SNS/블로그/커뮤니티/RSS
│    ├─ base.py         BaseCollector 인터페이스 + 레지스트리
│    ├─ news.py         구글뉴스 RSS(실수집), 네이버 검색 API, 다음
│    ├─ sns.py          X / 유튜브 / 인스타 (토큰 연동)
│    ├─ blog.py         네이버 블로그
│    ├─ community.py    디시/클리앙/fmkorea 등 어댑터 지점
│    └─ rss.py          공공 RSS / 보도자료
├─ analyze/           AI 분석 파이프라인 (PRD 7)
│    ├─ dedup.py        중복·유사·재배포 제거 (TF-IDF 코사인)
│    ├─ keywords.py     TF-IDF / Co-occurrence / TextRank
│    ├─ ner.py          개체명 인식 (사람/기관/지역/정책/예산/사업/기업)
│    ├─ cluster.py      토픽 군집화 (행정/경제/환경 ...)
│    ├─ sentiment.py    감성분석 (긍정/부정/중립/혼재)
│    ├─ volume.py       언급량·채널비중·일별추이
│    ├─ trend.py        급상승/급감/신규 키워드
│    ├─ summarize.py    추출 요약 (3/5/10줄)
│    └─ pipeline.py     오케스트레이터 (+ fixture 로드/재현성)
├─ llm/               공공기관 문체 서술 계층 (품질 핵심)
│    ├─ prompts.py      문체 헌장(STYLE_GUIDE) + 절별 grounded 프롬프트
│    ├─ providers.py    Gemini 2.5 Pro / OpenAI GPT-5 클라이언트
│    └─ narrator.py     TemplateNarrator(결정론) / LLMNarrator
├─ charts/            차트 렌더링 (PRD 9) — 언급량/감성/워드클라우드/네트워크 등
├─ report/            보고서 생성 (PRD 8·10)
│    ├─ docx_writer.py  DOCX (원본 절 구성 Ⅰ~Ⅵ 재현)
│    ├─ html_writer.py  HTML (차트 임베드)
│    └─ markdown_writer.py
├─ data/              분석결과 fixture (chungnam_202603.json)
└─ cli.py             실행 진입점
```

## 품질 설계 (PRD 12 대응)

| 목표 | 구현 |
|---|---|
| **수치 정확성** | 모든 통계는 `AnalysisResult` 데이터에서 렌더링. LLM 프롬프트에 "DATA에 없는 수치 생성 금지" 규칙 강제 (`llm/prompts.py`). |
| **출처 추적성** | 각 `Issue`/`CoreKeyword` 는 `evidence`(원문 URL) 보유. |
| **재현성** | 기본 `template` 서술 엔진은 결정론적. 시드 고정. 동일 입력 → 동일 출력. |
| **문체 일관성** | 개조식 음슴체(`~됨/~함/~임`), 3인칭 분석체를 STYLE_GUIDE + TemplateNarrator 로 통일. |
| **자동화율** | `collect → analyze → report` 무인 실행 (`cli.py`). |
| **확장성** | 대상/키워드/기간을 YAML 로 주입 → 타 지자체·기업·브랜드·인물 동일 적용. |

## LLM 서술 엔진 전환

기본은 **template**(API 키 불필요, 재현성 보장). 실 LLM 사용 시 설정에서
`llm.provider` 를 바꾸고 API 키를 환경변수로 제공:

```yaml
llm:
  provider: gemini      # 또는 openai
  model: gemini-2.5-pro # 또는 gpt-5
```
```bash
export GEMINI_API_KEY=...   # 또는 OPENAI_API_KEY
```
키가 없거나 호출 실패 시 자동으로 결정론적 template 로 안전하게 fallback.

## 라이브 수집 모드

`config` 에서 `data_fixture` 항목을 제거하면 `collectors` 목록이 실행된다.
인증이 필요한 수집기(네이버/X/유튜브/인스타)는 해당 환경변수가 있을 때만
동작하고, 없으면 빈 결과로 degrade 하므로 파이프라인은 중단되지 않는다.

| 수집기 | 필요 환경변수 |
|---|---|
| naver_news, naver_blog | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` |
| daum_news | `KAKAO_REST_API_KEY` |
| youtube | `YOUTUBE_API_KEY` |
| x | `X_BEARER_TOKEN` |
| instagram | `IG_ACCESS_TOKEN` |
| google_news, public_rss | (불필요) |

## HWP 출력

순수 `.hwp`(바이너리 독점 포맷) 직접 생성은 지원하지 않는다. 생성된 DOCX 를
한글(HWP)에서 열어 `다른 이름으로 저장 → .hwp` 로 변환하거나, LibreOffice
`soffice --convert-to` 파이프라인을 연결한다.
