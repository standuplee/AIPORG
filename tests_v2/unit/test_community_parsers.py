from datetime import datetime, timezone

from app.collectors.community.parsers import (
    ClienParser,
    DcinsideParser,
    FmkoreaParser,
    GenericParser,
    RuliwebParser,
    TheqooParser,
    get_parser,
)


def test_clien_parser_extracts_title_body_and_date_scoped_to_post_author() -> None:
    html = """
    <html><body>
      <div class="post_author">
        <span class="view_count date">2026-09-05 15:06:35</span>
      </div>
      <div class="post_subject">대전 전기차 보조금 공무원 사망 정리</div>
      <div class="post_article">본문 내용을 충분히 길게 작성해 둔 테스트용 문단입니다.</div>
      <span class="view_count">5,595</span>
    </body></html>
    """
    content = ClienParser().parse(html)
    assert content.ok
    assert content.title == "대전 전기차 보조금 공무원 사망 정리"
    assert "본문 내용을" in content.body
    assert content.posted_at == datetime(2026, 9, 5, 6, 6, 35, tzinfo=timezone.utc)


def test_fmkorea_parser_prefers_og_title_over_badge_span() -> None:
    # Confirmed live: h1.np_18px span matches a UI badge ("포텐"), not the
    # real title -- og:title carries the real one.
    html = """
    <html><head>
      <meta property="og:title" content="국축의 정석 - 대전 시티즌">
    </head><body>
      <div class="top_area">
        <span class="date m_no">2019.02.02 00:50</span>
      </div>
      <h1 class="np_18px"><span>포텐</span> 국축의 정석 - 대전 시티즌</h1>
      <article><div class="xe_content">대전시티즌 소개와 역사에 대한 충분히 긴 본문 문단입니다.</div></article>
    </body></html>
    """
    content = FmkoreaParser().parse(html)
    assert content.ok
    assert content.title == "국축의 정석 - 대전 시티즌"
    assert content.posted_at == datetime(2019, 2, 1, 15, 50, tzinfo=timezone.utc)


def test_theqoo_parser_uses_plain_title_class_and_side_fr_as_date_not_views() -> None:
    # Confirmed live: .title span/h1.title/.read_top .title all missed the
    # real title; plain .title (first match) is correct. .side.fr is the
    # post date, not a view count (the old selector misread it as one).
    html = """
    <html><body>
      <div class="title">대전 아자자 야채치킨</div>
      <div class="side fr">2026.06.14 19:19</div>
      <div class="rd_body"><div class="xe_content">충분히 긴 테스트용 게시글 본문 내용입니다.</div></div>
    </body></html>
    """
    content = TheqooParser().parse(html)
    assert content.ok
    assert content.title == "대전 아자자 야채치킨"
    assert content.views == 0
    assert content.posted_at == datetime(2026, 6, 14, 10, 19, tzinfo=timezone.utc)


def test_dcinside_parser_reads_full_timestamp_from_title_attribute() -> None:
    # Confirmed live: the visible text is truncated ("09.19"); the title
    # attribute on the first .gall_date carries the full timestamp.
    html = """
    <html><body>
      <span class="title_subject">국내야구 갤러리 서버 이전 되었습니다.</span>
      <span class="gall_date" title="2025-12-29 14:18:30">2025.12.29 14:18:30</span>
      <div class="write_div">공지 본문을 충분히 길게 작성해 둔 테스트 문단입니다.</div>
      <span class="gall_count">200,317</span>
    </body></html>
    """
    content = DcinsideParser().parse(html)
    assert content.ok
    assert content.title == "국내야구 갤러리 서버 이전 되었습니다."
    assert content.posted_at == datetime(2025, 12, 29, 5, 18, 30, tzinfo=timezone.utc)
    assert content.views == 200317


def test_dcinside_parser_falls_back_and_drops_unparseable_mini_gallery_markup() -> None:
    # The mini-gallery template (confirmed live) doesn't match any of the
    # known body selectors; GenericParser also can't find a real body in
    # it, so the post is dropped (ok=False) rather than collected wrong.
    html = "<html><head><title>mini gallery post</title></head><body><nav>메뉴</nav></body></html>"
    content = DcinsideParser().parse(html)
    assert content.ok is False


def test_ruliweb_parser_parses_parenthesized_regdate() -> None:
    html = """
    <html><body>
      <span class="subject_inner_text">슈로대Y를 디펜스 게임처럼 해 보자.</span>
      <span class="regdate">2026.08.28 (17:45:19)</span>
      <div class="view_content">충분히 긴 테스트용 루리웹 게시글 본문입니다.</div>
    </body></html>
    """
    content = RuliwebParser().parse(html)
    assert content.ok
    assert content.posted_at == datetime(2026, 8, 28, 8, 45, 19, tzinfo=timezone.utc)


def test_generic_parser_reads_article_published_time_meta() -> None:
    html = (
        '<html><head><title>Generic Title</title>'
        '<meta property="article:published_time" content="2026-07-20T10:00:00+09:00">'
        "</head><body><article>충분히 긴 일반 폴백 파서 테스트용 본문입니다.</article></body></html>"
    )
    content = GenericParser().parse(html)
    assert content.ok
    assert content.posted_at == datetime(2026, 7, 20, 1, 0, tzinfo=timezone.utc)


def test_generic_parser_drops_when_no_date_meta_present() -> None:
    html = "<html><head><title>No Date</title></head><body><article>본문은 있지만 날짜가 없는 케이스입니다 충분히 길게.</article></body></html>"
    content = GenericParser().parse(html)
    assert content.ok is False


def test_get_parser_returns_generic_for_unknown_site() -> None:
    assert isinstance(get_parser("unknown-site"), GenericParser)
