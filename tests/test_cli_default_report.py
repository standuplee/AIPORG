import json

from aiporg.cli import main


def test_default_report_type_still_accepts_existing_formats(tmp_path):
    out_dir = tmp_path / "out"
    main([
        "run",
        "--config", "config/chungnam_202606.yaml",
        "--formats", "json",
        "--out", str(out_dir),
    ])
    files = list(out_dir.glob("*_analysis.json"))
    assert files
    with files[0].open(encoding="utf-8") as fh:
        data = json.load(fh)
    assert "total_volume" in data
