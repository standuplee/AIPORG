from docx import Document as Docx

from aiporg.models_keyword_report import KeywordReportModel, KeywordReportSummary
from aiporg.report.keyword_docx_writer import write_keyword_docx


def test_write_keyword_docx_contains_required_headings(tmp_path):
    out = tmp_path / "keyword.docx"
    model = KeywordReportModel(
        summary=KeywordReportSummary(
            analysis_period="2026.07.01~2026.07.31",
            channel_count=6,
            primary_keyword="박수현",
            positive_ratio=58.0,
            month_over_month="▼3%p",
        )
    )

    write_keyword_docx(model, str(out), charts={})

    doc = Docx(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "CONTENTS" in text
    assert "REPORT SUMMARY" in text
    assert "제1장" in text
    assert "제6장" in text
