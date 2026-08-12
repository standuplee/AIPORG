from aiporg.charts.keyword_render import KeywordChartRenderer
from aiporg.models_keyword_report import KeywordReportModel


def test_keyword_chart_renderer_returns_mapping(tmp_path):
    renderer = KeywordChartRenderer(str(tmp_path))
    charts = renderer.render_all(KeywordReportModel())
    assert isinstance(charts, dict)
