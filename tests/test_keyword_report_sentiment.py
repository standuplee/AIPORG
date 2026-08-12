from aiporg.models import Channel, Document, Sentiment
from aiporg.analyze_keyword_report.sentiment import build_sentiment_drivers


def test_build_sentiment_drivers_extracts_positive_and_negative_groups():
    docs = [
        Document(doc_id="1", channel=Channel.NEWS, title="AI수도 충남 기대", body="일자리 기대", url="u1", sentiment=Sentiment.POSITIVE),
        Document(doc_id="2", channel=Channel.X, title="폭염 대응 비판", body="취약계층 대책 부족", url="u2", sentiment=Sentiment.NEGATIVE),
    ]
    pos, neg = build_sentiment_drivers(docs)
    assert pos
    assert neg
