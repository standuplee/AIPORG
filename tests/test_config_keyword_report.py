from aiporg.config import load_config


def test_load_config_parses_keyword_report_settings(tmp_path):
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text(
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
keyword_report:
  issue_keywords:
    AI수도 충남: [AI수도 충남, 충남 AI]
""",
        encoding="utf-8",
    )

    cfg = load_config(str(cfg_file))

    assert cfg.keyword_report.issue_keywords["AI수도 충남"] == ["AI수도 충남", "충남 AI"]
