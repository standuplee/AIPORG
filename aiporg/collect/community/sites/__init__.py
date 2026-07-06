"""사이트 파서 레지스트리."""
from __future__ import annotations

from .base import GenericParser, PostContent, SiteParser
from .clien import ClienParser
from .dcinside import DcinsideParser
from .fmkorea import FmkoreaParser
from .ruliweb import RuliwebParser
from .theqoo import TheqooParser

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


__all__ = ["PARSERS", "get_parser", "PostContent", "SiteParser", "GenericParser"]
