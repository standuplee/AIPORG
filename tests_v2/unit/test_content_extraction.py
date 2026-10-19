from unittest.mock import patch

from app.collectors.content_extraction import extract_article_text


_ARTICLE_HTML = """
<html><head><title>t</title></head>
<body>
<header><nav><a href="#">홈</a><a href="#">로그인</a><a href="#">검색</a></nav></header>
<div class="related-keywords">관련 키워드: 트럼프 이재명 국민연금 부동산</div>
<article>
<h1>충남도, 발전공기업 통합본사 유치 총력전</h1>
<p>충청남도가 발전공기업 통합본사를 유치하기 위해 총력을 기울이고 있다고 19일 밝혔다. 도 관계자는 지역 경제 활성화에 큰 도움이 될 것이라고 말했다.</p>
<p>충남도는 이번 유치전에 지역 국회의원들과 함께 공동 성명을 발표했으며, 중앙정부에 지속적으로 건의할 계획이라고 전했다.</p>
</article>
<footer>Copyright 2026. 모든 권리 보유. <a href="#">이용약관</a> <a href="#">개인정보처리방침</a></footer>
</body></html>
"""


def test_extract_article_text_drops_nav_header_footer_boilerplate() -> None:
    text = extract_article_text(_ARTICLE_HTML)

    assert "충청남도가 발전공기업 통합본사를 유치하기 위해" in text
    assert "중앙정부에 지속적으로 건의할 계획" in text
    for boilerplate in ("홈", "로그인", "관련 키워드", "이용약관", "개인정보처리방침", "Copyright"):
        assert boilerplate not in text


def test_extract_article_text_normalizes_whitespace_and_entities() -> None:
    html = "<html><script>bad()</script><body>첫 문장<br> 둘째 &amp; 셋째</body></html>"
    assert extract_article_text(html) == "첫 문장 둘째 & 셋째"


def test_extract_article_text_falls_back_to_whole_page_when_trafilatura_finds_nothing() -> None:
    # trafilatura.extract() returning None (it couldn't identify an article
    # shape) must not make the caller crash or come back empty -- the
    # legacy whole-page extractor is the safety net.
    with patch("app.collectors.content_extraction.trafilatura.extract", return_value=None):
        text = extract_article_text("<html><body><p>그래도 뭔가는 나와야 한다</p></body></html>")
    assert text == "그래도 뭔가는 나와야 한다"


def test_extract_article_text_excludes_reader_comments() -> None:
    html = """
    <article>
    <p>본문 내용입니다. 충분히 길게 작성된 실제 기사 문단입니다.</p>
    <p>두 번째 문단도 실제 기사 내용을 담고 있습니다.</p>
    </article>
    <section class="comments">
    <div class="comment">이건 독자 댓글입니다 삭제되어야 함</div>
    </section>
    """
    text = extract_article_text(html)
    assert "본문 내용입니다" in text
    assert "독자 댓글" not in text
