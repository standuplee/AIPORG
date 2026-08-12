from aiporg.models import Channel, Document
from aiporg.analyze_keyword_report.issues import rank_issues


def test_rank_issues_prefers_cluster_with_issue_keyword_hits():
    docs = [
        Document(doc_id="1", channel=Channel.NEWS, title="AI수도 충남 추진", body="충남 AI 3력 혁신", url="u1"),
        Document(doc_id="2", channel=Channel.X, title="AI수도 충남", body="AI수도 충남", url="u2"),
        Document(doc_id="3", channel=Channel.NEWS, title="기타 이슈", body="일반 내용", url="u3"),
    ]
    issues = rank_issues(docs, issue_keywords={"AI수도 충남": ["AI수도 충남", "충남 AI"]}, top_n=4)
    assert issues[0].title
    assert "AI" in issues[0].title or "AI" in issues[0].body
