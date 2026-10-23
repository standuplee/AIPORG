"""AIPORG 실행 진입점.

사용법:
    python -m aiporg.cli run --config config/chungnam_202606.yaml
    python -m aiporg.cli run --config <cfg> --formats docx,html,md --out output/

동작:
    1) 설정 로드
    2) 분석결과 확보  (fixture 로드 or 라이브 수집→분석)
    3) 차트 렌더링
    4) Narrator(공공기관 문체) 준비
    5) 보고서 파일 생성(DOCX/HTML/MD)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from .analyze import AnalysisPipeline
from .charts import ChartRenderer
from .charts.keyword_render import KeywordChartRenderer
from .analyze_keyword_report.periods import previous_month_range
from .analyze_keyword_report.pipeline import KeywordAnalysisPipeline
from .config import load_config
from .llm import build_narrator
from .models import ReportModel
from .report import write_docx, write_html, write_keyword_docx, write_markdown

log = logging.getLogger("aiporg")


def _resolve(path: str, base: str) -> str:
    return path if os.path.isabs(path) else os.path.join(base, path)


def run(args):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from .env import load_dotenv
    loaded = load_dotenv()
    if loaded:
        log.info(".env 로드: %s", ", ".join(loaded))
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = load_config(args.config)
    m = cfg.meta
    report_type = getattr(args, "report_type", "default")
    log.info("실행: %s / %s~%s / 대상=%s(%s)", m.report_title,
             m.period_start, m.period_end, m.subject_name, m.leader_name)
    if report_type == "keyword":
        if args.formats == "docx,html,md":
            args.formats = "docx"
        formats = [f.strip() for f in args.formats.split(",") if f.strip()]
        if any(fmt != "docx" for fmt in formats):
            raise SystemExit("keyword report currently supports only docx")
        return _run_keyword_report(args, cfg, project_root, formats)
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]

    pipeline = AnalysisPipeline(seed=cfg.seed)

    # --- 분석결과 확보 -------------------------------------------------- #
    if cfg.data_fixture:
        fixture = _resolve(cfg.data_fixture, project_root)
        log.info("fixture 로드: %s", fixture)
        analysis = pipeline.load_fixture(fixture)
    else:
        from .collect import build_registry
        log.info("라이브 수집: %s", ", ".join(cfg.collectors))
        registry = build_registry(cfg.collectors, cfg.max_docs_per_collector)
        all_kw = sorted({k for kws in m.keywords.values() for k in kws})
        docs = registry.run(all_kw, m.period_start, m.period_end)
        subjects = {"충남도청": m.keywords.get("충남도정", []),
                    "충남지사": m.keywords.get(f"충남지사({m.leader_name})", [])}
        # LLM provider 지정 시 감성 라벨링을 LLM 배치 분류로 업그레이드
        sclf = _llm_sentiment_classifier(cfg)
        analysis = pipeline.run(docs, m, subjects, sentiment_classifier=sclf)

    model = ReportModel(meta=m, analysis=analysis)

    # --- 분석결과 즉시 저장 (이후 단계 실패 시에도 수집·분석 산출물 보존) ---- #
    out_dir = _resolve(args.out, project_root)
    os.makedirs(out_dir, exist_ok=True)
    base = _basename(m)
    analysis.to_json(os.path.join(out_dir, base + "_analysis.json"))

    # --- 차트 ----------------------------------------------------------- #
    charts_dir = os.path.join(out_dir, "charts")
    log.info("차트 렌더링 -> %s", charts_dir)
    renderer = ChartRenderer(charts_dir)
    charts = renderer.render_all(analysis, subject=m.subject_name, meta=m)
    ok = sum(1 for v in charts.values() if v)
    log.info("차트 %d/%d 생성", ok, len(charts))

    # --- YouTube 채널 섹션(선택) --------------------------------------- #
    youtube_report = None
    if getattr(args, "youtube", "none") != "none":
        youtube_report = _run_youtube(m, args.youtube, project_root)
        if youtube_report is not None:
            charts.update(renderer.render_youtube(youtube_report))
            log.info("YouTube 섹션 포함: 영상 %d / 댓글 %d",
                     youtube_report.youtube_overview.video_count,
                     youtube_report.youtube_overview.comment_count)

    # --- Narrator ------------------------------------------------------- #
    narrator = build_narrator(cfg.llm_provider, cfg.llm_model, m, analysis)
    log.info("서술 엔진: %s", type(narrator).__name__)

    # --- 보고서 --------------------------------------------------------- #
    base = _basename(m)
    produced = []
    if "docx" in formats:
        p = write_docx(model, narrator, charts, os.path.join(out_dir, base + ".docx"),
                       youtube_report=youtube_report)
        produced.append(p)
    if "html" in formats:
        p = write_html(model, narrator, charts, os.path.join(out_dir, base + ".html"))
        produced.append(p)
    if "md" in formats:
        p = write_markdown(model, narrator, charts, os.path.join(out_dir, base + ".md"))
        produced.append(p)
    if "json" in formats:
        p = os.path.join(out_dir, base + "_analysis.json")
        analysis.to_json(p)
        produced.append(p)

    print("\n생성된 보고서:")
    for p in produced:
        size = os.path.getsize(p)
        print(f"  ✓ {p}  ({size:,} bytes)")
    return produced


def _run_keyword_report(args, cfg, project_root: str, formats: list[str]):
    from .collect import build_registry

    m = cfg.meta
    out_dir = _resolve(args.out, project_root)
    os.makedirs(out_dir, exist_ok=True)
    all_kw = sorted({k for kws in m.keywords.values() for k in kws})
    for kws in cfg.keyword_report.issue_keywords.values():
        all_kw.extend(kws)
    all_kw = sorted(set(all_kw))

    if cfg.data_fixture:
        log.info("keyword 보고서는 Document 기반 재분석이 필요하므로 data_fixture 는 무시하고 collectors 를 사용함")
    registry = build_registry(cfg.collectors, cfg.max_docs_per_collector)
    docs = registry.run(all_kw, m.period_start, m.period_end)
    prev_start, prev_end = previous_month_range(m.period_start, m.period_end)
    previous_docs = registry.run(all_kw, prev_start, prev_end)
    sclf = _llm_sentiment_classifier(cfg)
    _apply_sentiment_labels(docs, sclf)
    _apply_sentiment_labels(previous_docs, sclf)
    model = KeywordAnalysisPipeline().run(
        docs,
        previous_docs,
        m,
        issue_keywords=cfg.keyword_report.issue_keywords,
    )

    produced = []
    base = _basename(m) + "_keyword"
    charts_dir = os.path.join(out_dir, "charts")
    charts = KeywordChartRenderer(charts_dir).render_all(model)
    if "docx" in formats:
        p = write_keyword_docx(model, os.path.join(out_dir, base + ".docx"), charts=charts)
        produced.append(p)

    print("\n생성된 보고서:")
    for p in produced:
        size = os.path.getsize(p)
        print(f"  ✓ {p}  ({size:,} bytes)")
    return produced


def _llm_sentiment_classifier(cfg):
    """provider 가 gemini/openai 면 배치 감성 분류기를 반환, 아니면 None."""
    if cfg.llm_provider not in ("gemini", "openai"):
        return None
    try:
        if cfg.llm_provider == "gemini":
            from .llm.providers import GeminiClient
            client = GeminiClient(cfg.llm_model or "gemini-2.5-flash")
        else:
            from .llm.providers import OpenAIClient
            client = OpenAIClient(cfg.llm_model or "gpt-5")
    except Exception as e:  # noqa: BLE001
        log.warning("LLM 감성 분류기 준비 실패, 사전 기반 사용: %s", e)
        return None
    from .llm.sentiment_llm import classify_batch
    log.info("감성 분류: LLM(%s) 배치 모드", cfg.llm_provider)
    return lambda texts: classify_batch(client, texts)


def _apply_sentiment_labels(docs, sentiment_classifier):
    from .analyze import sentiment

    if sentiment_classifier is not None:
        texts = [d.title + " " + d.body for d in docs]
        labels = sentiment_classifier(texts)
        for doc, label in zip(docs, labels):
            doc.sentiment = label
        return
    for doc in docs:
        doc.sentiment = sentiment.classify(doc.title + " " + doc.body)


def _run_youtube(meta, mode: str, project_root: str):
    """YouTube 서브시스템 실행 → YouTubeReport (섹션 병합용). 실패/무데이터 시 None."""
    from .youtube.config import YouTubeConfig
    from .youtube.service import YouTubeService

    cfg = YouTubeConfig(
        period_start=meta.period_start, period_end=meta.period_end,
        subject_name=meta.subject_name, leader_title=meta.leader_title,
        leader_name=meta.leader_name,
        db_path=os.path.join(project_root, "data", "youtube.db"))
    client = None
    if mode == "mock":
        from .youtube.mock_data import MockApiClient
        client = MockApiClient()
    try:
        report = YouTubeService(cfg, client=client).run()
    except Exception as e:  # noqa: BLE001
        log.warning("YouTube 분석 실패(섹션 생략): %s", e)
        return None
    if report.youtube_overview.video_count == 0:
        log.warning("YouTube 수집 결과 없음(YOUTUBE_API_KEY 확인) → 섹션 생략")
        return None
    return report


def _basename(m) -> str:
    return f"{m.subject_name}{m.year}{m.month:02d}여론분석리포트({m.month}월)"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aiporg", description="AI 여론분석 보고서 생성기")
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="보고서 생성 실행")
    r.add_argument("--config", required=True, help="실행 설정 YAML 경로")
    r.add_argument("--out", default="output", help="출력 디렉터리")
    r.add_argument("--formats", default="docx,html,md", help="출력 형식 (docx,html,md,json)")
    r.add_argument("--report-type", choices=["default", "keyword"], default="default",
                   help="보고서 타입 선택")
    r.add_argument("--youtube", choices=["none", "mock", "live"], default="none",
                   help="유튜브 채널 섹션 포함 (mock=키없이 시연, live=YOUTUBE_API_KEY 사용)")
    r.set_defaults(func=run)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
