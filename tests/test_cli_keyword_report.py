from pathlib import Path

import pytest

from aiporg.cli import main


def test_keyword_report_rejects_non_docx_format():
    with pytest.raises(SystemExit) as excinfo:
        main([
            "run",
            "--config", "config/chungnam_202606.yaml",
            "--report-type", "keyword",
            "--formats", "docx,html",
        ])
    assert "only docx" in str(excinfo.value).lower()


def test_keyword_report_defaults_to_docx_when_formats_omitted(monkeypatch, tmp_path):
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

    class FakeRegistry:
        def run(self, keywords, start, end):
            del keywords, start, end
            return []

    outputs = []

    def fake_write_keyword_docx(model, out_path, charts=None):
        del model, charts
        Path(out_path).write_text("ok", encoding="utf-8")
        outputs.append(out_path)
        return out_path

    monkeypatch.setattr("aiporg.collect.build_registry", lambda names, max_docs: FakeRegistry())
    monkeypatch.setattr("aiporg.cli.write_keyword_docx", fake_write_keyword_docx)

    main([
        "run",
        "--config", str(cfg),
        "--report-type", "keyword",
        "--out", str(tmp_path / "out"),
    ])
    assert outputs and outputs[0].endswith(".docx")
