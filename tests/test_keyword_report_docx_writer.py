from docx import Document as Docx

from aiporg.models_keyword_report import (
    ChannelTrendItem,
    KeywordIssue,
    KeywordReportModel,
    KeywordReportSummary,
    RankedKeywordItem,
    SentimentDriver,
    SourceReference,
)
from aiporg.report.keyword_docx_writer import write_keyword_docx


def test_write_keyword_docx_contains_required_headings(tmp_path):
    out = tmp_path / "keyword.docx"
    model = KeywordReportModel(
        summary=KeywordReportSummary(
            analysis_period="2026.07.01~2026.07.31",
            channel_count=6,
            primary_keyword="박수현",
            positive_ratio=58.0,
            month_over_month="▼3%p",
        )
    )

    write_keyword_docx(model, str(out), charts={})

    doc = Docx(str(out))
    paragraphs = [p.text for p in doc.paragraphs if p.text]
    text = "\n".join(paragraphs)
    assert "CONTENTS" in text
    assert "REPORT SUMMARY" in text
    assert "분석기간: 2026.07.01~2026.07.31" in text
    assert "핵심 검색어: 박수현" in text
    chapter_positions = [text.index(label) for label in [
        "제1장 분석 개요",
        "제2장 월간 주요 이슈 동향",
        "제3장 온라인 채널별 여론 동향",
        "제4장 감성 분석 - 긍·부정 여론 동향",
        "제5장 시사점 및 도정 운영 제언",
        "제6장 출처 및 참고자료",
    ]]
    assert chapter_positions == sorted(chapter_positions)
    assert "수집 결과 없음" in text


def test_write_keyword_docx_renders_issue_and_source_content(tmp_path):
    out = tmp_path / "keyword-rich.docx"
    model = KeywordReportModel(
        summary=KeywordReportSummary(
            analysis_period="2026.07.01~2026.07.31",
            channel_count=6,
            primary_keyword="박수현",
            positive_ratio=58.0,
            month_over_month="▼3%p",
        ),
        issues=[
            KeywordIssue(rank=1, title="AI수도 충남", subtitle="주요 이슈", body="충남 AI 산업 전환 기대", evidence=["https://example.com/1"]),
        ],
        channel_overview=[
            ChannelTrendItem(channel="뉴스기사", share_or_volume=12, change_direction="▲ 증가", keywords=["AI수도 충남"]),
        ],
        top_keywords=[
            RankedKeywordItem(rank=1, keyword="AI수도 충남", category="산업/기술"),
        ],
        positive_drivers=[
            SentimentDriver(sentiment="긍정", title="산업 기대감", detail="일자리 기대 확산", evidence=["https://example.com/1"]),
        ],
        implications=[
            {"topic": "AI수도 충남", "headline": "홍보 강화 필요", "body": "성과 메시지 확산"},
        ],
        channel_recommendations=[
            {"channel": "온라인 채널", "action": "영상·기사 동시 배포"},
        ],
        sources=[
            SourceReference(source_id="1", title="AI 기사", url="https://example.com/1", channel="뉴스기사"),
        ],
        methodology=["키워드 기반 수집", "감성 분석"],
    )

    write_keyword_docx(model, str(out), charts={})

    doc = Docx(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "AI수도 충남" in text
    assert "뉴스기사" in text
    assert "산업 기대감" in text
    assert "AI 기사" in text
