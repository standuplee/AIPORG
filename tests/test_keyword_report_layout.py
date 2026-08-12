from aiporg.report.keyword_layout import summary_labels


def test_summary_labels_contains_required_fields():
    labels = summary_labels()
    assert "분석기간" in labels
    assert "핵심 검색어" in labels
