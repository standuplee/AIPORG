from aiporg.models_keyword_report import KeywordReportModel, KeywordReportSummary


def test_keyword_report_model_to_dict_roundtrip():
    model = KeywordReportModel(
        summary=KeywordReportSummary(
            analysis_period="2026.07.01~2026.07.31",
            channel_count=6,
            primary_keyword="박수현",
            positive_ratio=58.0,
            month_over_month="▼3%p",
        )
    )

    raw = model.to_dict()
    restored = KeywordReportModel.from_dict(raw)

    assert restored.summary.primary_keyword == "박수현"
