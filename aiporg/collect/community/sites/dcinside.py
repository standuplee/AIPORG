"""디시인사이드 게시글 파서 (공개 HTML 본문만).

주의: 사이트 구조는 변경될 수 있으므로 selector 는 운영 시 검증 필요.
실패 시 GenericParser 로 폴백한다.
"""
from __future__ import annotations

from .base import GenericParser, PostContent, SiteParser, _first_text, _num, soup

TITLE_SEL = [".title_subject", ".gallview_head .title .title_subject", "h3.title"]
BODY_SEL = [".write_div", ".writing_view_box", ".gallview_contents .inner"]


def _pick(s, selectors):
    for sel in selectors:
        node = s.select_one(sel)
        if node:
            return node
    return None


class DcinsideParser(SiteParser):
    site = "dcinside"

    def parse(self, html: str) -> PostContent:
        s = soup(html)
        title = _first_text(_pick(s, TITLE_SEL))
        body_node = _pick(s, BODY_SEL)
        if not body_node:
            return GenericParser().parse(html)
        for t in body_node(["script", "style"]):
            t.decompose()
        pc = PostContent(
            title=title, body=_first_text(body_node),
            views=_num(_first_text(s.select_one(".gall_count"))),
            likes=_num(_first_text(s.select_one(".up_num"))),
            comment_count=_num(_first_text(s.select_one(".comment_count"))),
        ).clean()
        return pc
