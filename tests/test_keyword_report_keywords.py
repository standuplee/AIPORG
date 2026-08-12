from aiporg.models import Channel, Document
from aiporg.analyze_keyword_report.keywords import top_ranked_keywords


def test_top_ranked_keywords_returns_ranked_categorized_items():
    docs = [
        Document(doc_id="1", channel=Channel.NEWS, title="청년AI인재 양성", body="충남 AI 인재", url="u1"),
        Document(doc_id="2", channel=Channel.X, title="민생지원금 확대", body="민생지원금", url="u2"),
    ]
    items = top_ranked_keywords(docs, top_n=5)
    assert items[0].rank == 1
    assert items[0].category
