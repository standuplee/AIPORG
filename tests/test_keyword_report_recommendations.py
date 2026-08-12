from aiporg.models_keyword_report import KeywordIssue, SentimentDriver
from aiporg.analyze_keyword_report.recommendations import build_recommendations


def test_build_recommendations_returns_implications_and_channel_actions():
    issues = [KeywordIssue(rank=1, title="폭염 기후재난", subtitle="", body="폭염 대응 이슈", evidence=[], source_notes=[])]
    negative = [SentimentDriver(sentiment="부정", title="폭염 대응 비판", detail="취약계층 대책 부족", evidence=[])]
    implications, channel_actions = build_recommendations(issues, [], negative)
    assert implications
    assert channel_actions
