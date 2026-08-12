from aiporg.models import Channel, Document
from aiporg.analyze_keyword_report.channels import build_channel_trends


def test_build_channel_trends_returns_change_direction():
    current_docs = [Document(doc_id="1", channel=Channel.X, title="폭염", body="기후재난", url="u1")]
    previous_docs = []
    items = build_channel_trends(current_docs, previous_docs)
    assert items[0].change_direction in {"▲ 증가", "▼ 감소", "— 유지", "비교 불가"}
