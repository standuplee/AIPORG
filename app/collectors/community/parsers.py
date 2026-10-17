"""Site-specific HTML parsers for community posts.

Ported from ``aiporg/collect/community/sites/*.py`` (1.0), then verified and
fixed live against real posts on all five sites (same methodology used
throughout this collector porting effort: fetch a real page, run the parser
against it, and look at what actually came out -- not just read the
selectors and assume they still match). Three real, confirmed bugs in the
1.0 selectors were fixed along the way; see each parser's docstring for the
specific live evidence.

Biggest structural change from 1.0: 1.0's parsers never extracted a publish
date at all (``PostContent.posted_at`` existed on the dataclass but no site
parser ever set it -- 1.0's own SQLite store just recorded a NULL
``posted_at`` for every community post it ever collected). 2.0's
``SearchResult.published_at`` is a required field, so every parser here adds
real date extraction from a selector verified against a live page, and
``PostContent.ok`` now also requires a parsed date. A post whose date cannot
be parsed is dropped rather than given a fabricated timestamp -- the same
policy ``app/collectors/google_search.py`` already applies for the same kind
of gap ("게시 시각을 확인할 수 없는 자료는 보류", 2026-10-16 decision).

Privacy: unchanged from 1.0. No parser extracts an author nickname or
comment text -- only the post's own title, body, and aggregate counts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

_KST = timezone(timedelta(hours=9))


@dataclass
class PostContent:
    title: str = ""
    body: str = ""
    posted_at: datetime | None = None
    views: int = 0
    likes: int = 0
    comment_count: int = 0

    @property
    def ok(self) -> bool:
        return bool(self.body and len(self.body) >= 20 and self.posted_at is not None)

    def clean(self) -> "PostContent":
        self.title = _norm(self.title)
        self.body = _norm(self.body)
        return self


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _first_text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _num(text: str) -> int:
    match = re.search(r"[\d,]+", text or "")
    return int(match.group(0).replace(",", "")) if match else 0


def _pick(soup: BeautifulSoup, selectors: list[str]):
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            return node
    return None


def _parse_kst(text: str | None, fmt: str) -> datetime | None:
    if not text:
        return None
    try:
        naive = datetime.strptime(text.strip(), fmt)
    except ValueError:
        return None
    return naive.replace(tzinfo=_KST).astimezone(timezone.utc)


def _og_title(soup: BeautifulSoup) -> str:
    tag = soup.find("meta", property="og:title")
    content = tag.get("content") if tag else None
    return _norm(content) if isinstance(content, str) else ""


def _generic_posted_at(soup: BeautifulSoup) -> datetime | None:
    """Last-resort date lookup for the generic fallback parser.

    Mirrors the ``pagemap.metatags`` ``article:published_time`` convention
    ``app/collectors/google_search.py`` already relies on for pages with no
    site-specific parser.
    """
    for prop in ("article:published_time", "og:updated_time"):
        tag = soup.find("meta", property=prop)
        content = tag.get("content") if tag else None
        if isinstance(content, str) and content.strip():
            try:
                parsed = datetime.fromisoformat(content.strip())
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=_KST)
            return parsed.astimezone(timezone.utc)
    return None


class SiteParser:
    site = "generic"

    def parse(self, html: str) -> PostContent:
        raise NotImplementedError


class GenericParser(SiteParser):
    """Conservative fallback for markup with no site-specific parser or a stale one."""

    site = "generic"

    def parse(self, html: str) -> PostContent:
        soup = _soup(html)
        for tag in soup(["script", "style", "nav", "header", "footer", "form"]):
            tag.decompose()
        title = _first_text(soup.title) if soup.title else ""
        candidate = soup.find("article") or soup.find("main")
        if candidate is None:
            divs = soup.find_all("div")
            candidate = max(divs, key=lambda d: len(d.get_text(" ", strip=True)), default=None)
        body = _first_text(candidate)
        return PostContent(title=title, body=body, posted_at=_generic_posted_at(soup)).clean()


class ClienParser(SiteParser):
    site = "clien"

    TITLE_SEL = [".post_subject span", ".post_subject", "h3.post_subject"]
    BODY_SEL = [".post_article", ".post_content", "div.post_view"]
    # Scoped to .post_author so this can't pick up a comment's own .date node.
    DATE_SEL = [".post_author .date"]

    def parse(self, html: str) -> PostContent:
        soup = _soup(html)
        body = _pick(soup, self.BODY_SEL)
        if not body:
            return GenericParser().parse(html)
        for tag in body(["script", "style"]):
            tag.decompose()
        return PostContent(
            title=_first_text(_pick(soup, self.TITLE_SEL)),
            body=_first_text(body),
            posted_at=_parse_kst(_first_text(_pick(soup, self.DATE_SEL)), "%Y-%m-%d %H:%M:%S"),
            views=_num(_first_text(soup.select_one(".view_count"))),
        ).clean()


class DcinsideParser(SiteParser):
    """Covers the standard ("정식") gallery template.

    Confirmed live that the "미니 갤러리" template (``/mini/board/view/``
    URLs) uses different markup and does not match these selectors -- it
    falls through to ``GenericParser``, which also fails to find a usable
    body on it in practice, so mini-gallery posts are silently dropped
    (``PostContent.ok`` is False) rather than collected wrong. A third,
    mini-gallery-specific parser is out of scope for this pass.
    """

    site = "dcinside"

    TITLE_SEL = [".title_subject", ".gallview_head .title .title_subject", "h3.title"]
    BODY_SEL = [".write_div", ".writing_view_box", ".gallview_contents .inner"]
    # The visible text is often truncated ("09.19"); the title attribute
    # carries the full timestamp. Confirmed live on a real post.
    DATE_SEL = ".gall_date[title]"

    def parse(self, html: str) -> PostContent:
        soup = _soup(html)
        title = _first_text(_pick(soup, self.TITLE_SEL))
        body_node = _pick(soup, self.BODY_SEL)
        if not body_node:
            return GenericParser().parse(html)
        for tag in body_node(["script", "style"]):
            tag.decompose()
        date_node = soup.select_one(self.DATE_SEL)
        posted_at = _parse_kst(date_node.get("title") if date_node else None, "%Y-%m-%d %H:%M:%S")
        return PostContent(
            title=title,
            body=_first_text(body_node),
            posted_at=posted_at,
            views=_num(_first_text(soup.select_one(".gall_count"))),
            likes=_num(_first_text(soup.select_one(".up_num"))),
            comment_count=_num(_first_text(soup.select_one(".comment_count"))),
        ).clean()


class FmkoreaParser(SiteParser):
    """``og:title`` is preferred over the old selector.

    Confirmed live: ``h1.np_18px span`` (the old ``TITLE_SEL[0]``) matched a
    UI badge ("포텐") on a real post, not the title ("국축의 정석 - 대전
    시티즌"). ``og:title`` carries the clean title with no badge text.
    """

    site = "fmkorea"

    TITLE_SEL_FALLBACK = ["h1.np_18px span", ".np_18px", "h1.title", ".top_area .title"]
    BODY_SEL = ["article .rd_body .xe_content", ".xe_content", "article .document_content"]
    # Scoped to .top_area so this can't pick up a comment's own .date node
    # (confirmed live: fmkorea reuses the bare .date class for comment
    # timestamps too, further down the same page).
    DATE_SEL = [".top_area .date", ".date"]

    def parse(self, html: str) -> PostContent:
        soup = _soup(html)
        body = _pick(soup, self.BODY_SEL)
        if not body:
            return GenericParser().parse(html)
        for tag in body(["script", "style"]):
            tag.decompose()
        title = _og_title(soup) or _first_text(_pick(soup, self.TITLE_SEL_FALLBACK))
        return PostContent(
            title=title,
            body=_first_text(body),
            posted_at=_parse_kst(_first_text(_pick(soup, self.DATE_SEL)), "%Y.%m.%d %H:%M"),
            views=_num(_first_text(soup.select_one(".side.fr"))),
        ).clean()


class RuliwebParser(SiteParser):
    site = "ruliweb"

    TITLE_SEL = [".subject_inner_text", ".subject_text .subject_inner_text", "h1.subject"]
    BODY_SEL = [".view_content", ".board_main_view .view_content", "article .content"]
    DATE_SEL = [".regdate"]

    def parse(self, html: str) -> PostContent:
        soup = _soup(html)
        body = _pick(soup, self.BODY_SEL)
        if not body:
            return GenericParser().parse(html)
        for tag in body(["script", "style"]):
            tag.decompose()
        return PostContent(
            title=_first_text(_pick(soup, self.TITLE_SEL)),
            body=_first_text(body),
            posted_at=_parse_kst(
                _first_text(_pick(soup, self.DATE_SEL)), "%Y.%m.%d (%H:%M:%S)"
            ),
            views=_num(_first_text(soup.select_one(".view_count"))),
        ).clean()


class TheqooParser(SiteParser):
    """``.title`` (not ``.title span``) and ``.side.fr`` as the date, not views.

    Confirmed live against a real post: the old ``TITLE_SEL`` (``.title
    span``, ``h1.title``, ``.read_top .title``) matched none of them and
    fell through to an unrelated node reading literally "제목" (a related-
    posts table's column header), producing an empty/wrong title. Plain
    ``.title`` is the post's own title node (first match in DOM order).

    Separately, the old ``views`` selector (``.side.fr``) was reading this
    same post-date text and running it through a digit-extraction regex,
    silently turning "2026.06.14 19:19" into a bogus view count of 2026 (the
    year). theqoo's real view count is not present in this page's static
    HTML at all (likely script-rendered), so ``views`` is left at 0 here
    rather than guessed, and ``.side.fr`` is used for what it actually is.
    """

    site = "theqoo"

    TITLE_SEL = [".title"]
    BODY_SEL = [".rd_body .xe_content", ".xe_content", ".read_body"]
    DATE_SEL = [".side.fr"]

    def parse(self, html: str) -> PostContent:
        soup = _soup(html)
        body = _pick(soup, self.BODY_SEL)
        if not body:
            return GenericParser().parse(html)
        for tag in body(["script", "style"]):
            tag.decompose()
        return PostContent(
            title=_first_text(_pick(soup, self.TITLE_SEL)),
            body=_first_text(body),
            posted_at=_parse_kst(_first_text(_pick(soup, self.DATE_SEL)), "%Y.%m.%d %H:%M"),
        ).clean()


PARSERS: dict[str, SiteParser] = {
    "dcinside": DcinsideParser(),
    "clien": ClienParser(),
    "fmkorea": FmkoreaParser(),
    "theqoo": TheqooParser(),
    "ruliweb": RuliwebParser(),
}

_GENERIC = GenericParser()


def get_parser(site: str) -> SiteParser:
    return PARSERS.get(site, _GENERIC)


# A discovered URL's path+query must look like an individual post, not a
# board/gallery/category listing page, before it is worth spending a site's
# rate-limit budget on fetching it. Found live: Naver web search surfaces
# both kinds for every one of these five sites, and a listing page never
# parses as a post (no title/body/date to extract), so filtering here saves
# requests that were never going to produce a document.
#
# fmkorea's pattern expects the board-prefixed form
# (/best|/best2|/humor/<id>), not the bare /<id> fmkorea.com also serves --
# see FMKOREA_BOARDS and extract_fmkorea_board_post_ids() below for why.
POST_URL_PATTERNS: dict[str, re.Pattern[str]] = {
    "dcinside": re.compile(r"/board/view/"),
    "clien": re.compile(r"/service/board/[^/?]+/\d+"),
    "fmkorea": re.compile(r"^/(?:best2?|humor)/\d+(?:[/?]|$)"),
    "ruliweb": re.compile(r"/read/\d+"),
    "theqoo": re.compile(r"/\d+(?:[/?]|$)"),
}


# fmkorea's robots.txt (confirmed live, 2026-10-17) denies every path to
# unnamed/generic bots except "/", "/best", "/best2", and "/humor" -- an
# individual post's canonical URL is a bare numeric path (e.g.
# "fmkorea.com/1234567890") that matches none of those, so it is always
# disallowed regardless of which board the post is actually in. The *same*
# post is also reachable at "fmkorea.com/<board>/<id>" (confirmed live: both
# forms return identical content), and that form IS allowed when <board> is
# one of these three.
#
# This only legitimately applies to a post that is genuinely linked from
# that board's own listing page right now -- stamping an arbitrary
# Naver-discovered id with "/best/" to make robots.txt's pattern match,
# regardless of whether the post actually is a /best post, would satisfy the
# literal rule while defeating its obvious intent (the operator scoped
# access to these boards' content, not to every post on the site). So
# membership is never assumed: collector.py fetches each board's own
# listing page and only treats an id as belonging to a board if this
# extractor actually found it linked there.
FMKOREA_BOARDS = ("best", "best2", "humor")


def extract_fmkorea_board_post_ids(html: str, board: str) -> list[str]:
    """Post ids linked from one fmkorea board listing page, in page order.

    best/best2 link posts with a board-prefixed href ("/best/<id>",
    confirmed live); humor links posts with a bare numeric href ("/<id>")
    even on its own listing page, so a bare numeric link found *on this
    specific listing page* is accepted only for board == "humor".
    """
    soup = _soup(html)
    ids: list[str] = []
    seen: set[str] = set()
    prefix = f"/{board}/"
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        path = href.split("?", 1)[0]
        if board in ("best", "best2"):
            if not path.startswith(prefix):
                continue
            candidate = path[len(prefix):].rstrip("/")
        else:
            candidate = path.strip("/")
        # A 5+ digit numeric id filters out pagination links ("?page=2"
        # never reaches here anyway), nav anchors, and other short numeric
        # hrefs that are not post ids.
        if candidate.isdigit() and len(candidate) >= 5 and candidate not in seen:
            seen.add(candidate)
            ids.append(candidate)
    return ids
