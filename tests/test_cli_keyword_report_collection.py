from pathlib import Path

from aiporg.cli import main
from aiporg.models import Channel, Document


def test_keyword_report_run_collects_current_and_previous_month(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        """
project_name: 충청남도
subject:
  name: 충청남도
  leader_title: 도지사
  leader_name: 박수현
period:
  start: 2026.07.01
  end: 2026.07.31
report_title: 2026년 7월 충청남도 온라인 여론 분석
keywords:
  충청남도: [충남, 박수현]
collectors: [google_news]
keyword_report:
  issue_keywords:
    AI수도 충남: [AI수도 충남]
""",
        encoding="utf-8",
    )

    calls = []

    class FakeRegistry:
        def run(self, keywords, start, end):
            calls.append((tuple(sorted(keywords)), start.isoformat(), end.isoformat()))
            return [
                Document(
                    doc_id=f"{start.isoformat()}",
                    channel=Channel.NEWS,
                    title="AI수도 충남",
                    body="충남 AI",
                    url=f"https://example.com/{start.isoformat()}",
                )
            ]

    def fake_build_registry(names, max_docs):
        assert names == ["google_news"]
        assert max_docs == 200
        return FakeRegistry()

    def fake_write_keyword_docx(model, out_path, charts=None):
        del model, charts
        Path(out_path).write_text("ok", encoding="utf-8")
        return out_path

    monkeypatch.setattr("aiporg.collect.build_registry", fake_build_registry)
    monkeypatch.setattr("aiporg.cli.write_keyword_docx", fake_write_keyword_docx)

    main([
        "run",
        "--config", str(cfg),
        "--report-type", "keyword",
        "--formats", "docx",
        "--out", str(tmp_path / "out"),
    ])

    assert len(calls) == 2
    assert calls[0][1:] == ("2026-07-01", "2026-07-31")
    assert calls[1][1:] == ("2026-06-01", "2026-06-30")
