from aiporg.models import Channel, Document
from aiporg.analyze_keyword_report.sources import build_source_references


def test_build_source_references_deduplicates_urls():
    docs = [
        Document(doc_id="1", channel=Channel.NEWS, title="t1", body="b", url="https://x/1"),
        Document(doc_id="2", channel=Channel.NEWS, title="t1 copy", body="b", url="https://x/1"),
    ]
    refs = build_source_references(docs)
    assert len(refs) == 1
