from pathlib import Path

from aiporg.cli import main
from aiporg.models import Channel, Document


def test_keyword_report_e2e_generates_docx(tmp_path, monkeypatch):
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
    AI수도 충남: [AI수도 충남, 충남 AI]
""",
        encoding="utf-8",
    )

    class FakeRegistry:
        def run(self, keywords, start, end):
            del keywords, start, end
            return [
                Document(
                    doc_id="1",
                    channel=Channel.NEWS,
                    title="AI수도 충남",
                    body="충남 AI 산업 전환 기대",
                    url="https://example.com/1",
                )
            ]

    monkeypatch.setattr("aiporg.collect.build_registry", lambda names, max_docs: FakeRegistry())

    out_dir = tmp_path / "out"
    main([
        "run",
        "--config", str(cfg),
        "--report-type", "keyword",
        "--formats", "docx",
        "--out", str(out_dir),
    ])
    files = list(out_dir.glob("*.docx"))
    assert files
