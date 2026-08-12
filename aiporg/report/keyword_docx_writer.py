"""키워드 조사 보고서 DOCX writer."""
from __future__ import annotations

from docx import Document as Docx

from ..models_keyword_report import KeywordReportModel
from .keyword_layout import summary_labels, toc_items
from .keyword_sections import fallback_text


def write_keyword_docx(model: KeywordReportModel, out_path: str, charts: dict | None = None) -> str:
    del charts
    doc = Docx()
    doc.add_paragraph("2026년 여론분석컨설팅 리포트")
    doc.add_paragraph("CONTENTS")
    for item in toc_items():
        doc.add_paragraph(item)

    doc.add_paragraph("REPORT SUMMARY")
    values = [
        model.summary.analysis_period,
        str(model.summary.channel_count),
        model.summary.primary_keyword,
        str(model.summary.positive_ratio),
        model.summary.month_over_month,
    ]
    for label, value in zip(summary_labels(), values):
        doc.add_paragraph(f"{label}: {value}")

    for title in toc_items():
        doc.add_paragraph(title)
        text = fallback_text(False)
        if text:
            doc.add_paragraph(text)

    doc.save(out_path)
    return out_path
