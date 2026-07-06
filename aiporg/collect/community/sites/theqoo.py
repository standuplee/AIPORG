"""더쿠 게시글 파서 (공개 HTML 본문만). selector 는 운영 시 검증 필요."""
from __future__ import annotations

from .base import GenericParser, PostContent, SiteParser, _first_text, soup

TITLE_SEL = [".title span", "h1.title", ".read_top .title"]
BODY_SEL = [".rd_body .xe_content", ".xe_content", ".read_body"]


def _pick(s, sels):
    for sel in sels:
        n = s.select_one(sel)
        if n:
            return n
    return None


class TheqooParser(SiteParser):
    site = "theqoo"

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
        ).clean()
