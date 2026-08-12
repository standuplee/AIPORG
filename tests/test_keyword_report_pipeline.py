from datetime import date

from aiporg.analyze_keyword_report.pipeline import KeywordAnalysisPipeline
from aiporg.models import Channel, Document, ReportMeta


def test_keyword_pipeline_builds_keyword_report_model():
    meta = ReportMeta(
        project_name="충청남도",
        subject_name="충청남도",
        leader_title="도지사",
        leader_name="박수현",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        keywords={"충청남도": ["충남", "박수현"]},
        report_title="test",
    )
    docs = [Document(doc_id="1", channel=Channel.NEWS, title="AI수도 충남", body="충남 AI", url="u1")]
    model = KeywordAnalysisPipeline().run(docs, [], meta, issue_keywords={"AI수도 충남": ["AI수도 충남"]})
    assert model.issues
    assert model.summary.primary_keyword == "박수현"
