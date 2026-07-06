"""사이트별 HTML 파서 베이스.

2차 단계: 공개 HTML 페이지의 '게시글 본문'만 파싱한다.
개인정보 보호: 작성자 닉네임/프로필/댓글 본문은 추출하지 않는다(제목·본문·집계수치만).
각 파서는 사이트 구조에 맞는 selector 를 제공하고, 실패 시 GenericParser 로 폴백.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class PostContent:
    title: str = ""
    body: str = ""
    posted_at: str | None = None     # ISO 문자열(가능 시)
    views: int = 0
    likes: int = 0
    comment_count: int = 0
    ok: bool = False                 # 유효 본문 추출 성공 여부

    def clean(self) -> "PostContent":
        self.title = _norm(self.title)
        self.body = _norm(self.body)
        self.ok = bool(self.body and len(self.body) >= 20)
        return self


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


class SiteParser:
    """사이트 파서 인터페이스."""

    site: str = "generic"

    def parse(self, html: str) -> PostContent:
        raise NotImplementedError


def soup(html: str):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "lxml")


def _first_text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _num(text: str) -> int:
    m = re.search(r"[\d,]+", text or "")
    return int(m.group(0).replace(",", "")) if m else 0


class GenericParser(SiteParser):
    """구조를 모르는 경우의 보수적 폴백: <title> + 최대 텍스트 블록."""

    site = "generic"

    def parse(self, html: str) -> PostContent:
        s = soup(html)
        for tag in s(["script", "style", "nav", "header", "footer", "form"]):
            tag.decompose()
        title = _first_text(s.title) if s.title else ""
        # 본문 후보: article/main, 없으면 최대 길이 <div>
        cand = s.find("article") or s.find("main")
        if cand is None:
            divs = s.find_all("div")
            cand = max(divs, key=lambda d: len(d.get_text(" ", strip=True)), default=None)
        body = _first_text(cand)
        return PostContent(title=title, body=body).clean()
