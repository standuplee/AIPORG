"""커뮤니티 수집 정책 로더.

config/community.yaml 을 읽어 사이트별 SitePolicy 로 변환한다. 기본값은
defaults 로 채우고, 사이트는 enabled=false 로 시작(운영자 ToS 검토 필수).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import yaml


@dataclass
class SitePolicy:
    name: str
    enabled: bool
    domains: list[str]
    search_hints: list[str]
    user_agent: str
    min_interval_sec: float
    max_requests_per_run: int
    request_timeout_sec: int
    respect_robots: bool
    store_author: bool
    store_comments_text: bool
    exclude_patterns: list[str] = field(default_factory=list)

    def __post_init__(self):
        self._exclude = [re.compile(p) for p in self.exclude_patterns]

    def matches_domain(self, host: str) -> bool:
        host = (host or "").lower()
        return any(host == d or host.endswith("." + d) or host == d for d in self.domains)

    def is_excluded(self, url: str) -> bool:
        return any(p.search(url) for p in self._exclude)


DEFAULTS = {
    "user_agent": "AIPORG-Research-Bot/1.0 (+respect-robots)",
    "min_interval_sec": 3.0,
    "max_requests_per_run": 25,
    "request_timeout_sec": 10,
    "respect_robots": True,
    "store_author": False,
    "store_comments_text": False,
}


def _root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))


def load_policies(path: str | None = None) -> dict[str, SitePolicy]:
    if path is None:
        path = os.path.join(_root(), "config", "community.yaml")
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    d = {**DEFAULTS, **(raw.get("defaults") or {})}
    out: dict[str, SitePolicy] = {}
    for name, s in (raw.get("sites") or {}).items():
        s = s or {}
        out[name] = SitePolicy(
            name=name,
            enabled=bool(s.get("enabled", False)),
            domains=s.get("domains", []),
            search_hints=s.get("search_hints", [name]),
            user_agent=s.get("user_agent", d["user_agent"]),
            min_interval_sec=float(s.get("min_interval_sec", d["min_interval_sec"])),
            max_requests_per_run=int(s.get("max_requests_per_run", d["max_requests_per_run"])),
            request_timeout_sec=int(s.get("request_timeout_sec", d["request_timeout_sec"])),
            respect_robots=bool(s.get("respect_robots", d["respect_robots"])),
            store_author=bool(s.get("store_author", d["store_author"])),
            store_comments_text=bool(s.get("store_comments_text", d["store_comments_text"])),
            exclude_patterns=s.get("exclude_patterns", []),
        )
    return out
