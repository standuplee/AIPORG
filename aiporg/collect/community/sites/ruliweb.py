"""루리웹 게시글 파서 (공개 HTML 본문만). selector 는 운영 시 검증 필요."""
from __future__ import annotations

from .base import GenericParser, PostContent, SiteParser, _first_text, _num, soup

TITLE_SEL = [".subject_inner_text", ".subject_text .subject_inner_text", "h1.subject"]
BODY_SEL = [".view_content", ".board_main_view .view_content", "article .content"]


def _pick(s, sels):
    for sel in sels:
        n = s.select_one(sel)
        if n:
            return n
    return None


class RuliwebParser(SiteParser):
    site = "ruliweb"

    def parse(self, html: str) -> PostContent:
        s = soup(html)
        body = _pick(s, BODY_SEL)
        if not body:
            return GenericParser().parse(html)
        for t in body(["script", "style"]):
            t.decompose()
        return PostContent(
            title=_first_text(_pick(s, TITLE_SEL)),
            body=_first_text(body),
            views=_num(_first_text(s.select_one(".view_count"))),
        ).clean()
