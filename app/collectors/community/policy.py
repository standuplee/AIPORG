"""Per-site community collection policy, loaded from ``config/community.yaml``.

Ported from ``aiporg/collect/community/policy.py`` (1.0). The file and the
safety gate it enforces are reused as-is, not duplicated: every site defaults
to ``enabled: false`` until an operator has personally reviewed that site's
robots.txt and terms of service and flipped it on in the shared YAML file.
Both 1.0 and 2.0 read the same ``config/community.yaml``, so there is one
enable/disable decision per site, not two that could drift apart.

Simplification versus 1.0: the ``store_author``/``store_comments_text``
policy toggles are dropped. 1.0 used them to let an operator opt back into
collecting author nicknames or comment text; 2.0's parsers structurally never
extract either field at all (no toggle to collect what the code cannot
produce), so the privacy principle ("작성자 닉네임/프로필/댓글 본문은 수집하지
않는다") is enforced by the parser, not a configurable flag.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "community.yaml"

DEFAULTS = {
    "user_agent": "AIPORG-Research-Bot/1.0 (+respect-robots)",
    "min_interval_sec": 3.0,
    "max_requests_per_run": 25,
    "request_timeout_sec": 10,
    "respect_robots": True,
}


@dataclass(frozen=True)
class SitePolicy:
    name: str
    enabled: bool
    domains: tuple[str, ...]
    search_hints: tuple[str, ...]
    user_agent: str
    min_interval_sec: float
    max_requests_per_run: int
    request_timeout_sec: int
    respect_robots: bool
    exclude_patterns: tuple[str, ...] = ()

    def matches_domain(self, host: str) -> bool:
        host = (host or "").lower()
        return any(host == domain or host.endswith(f".{domain}") for domain in self.domains)

    def is_excluded(self, url: str) -> bool:
        return any(re.search(pattern, url) for pattern in self.exclude_patterns)


def load_policies(path: str | Path | None = None) -> dict[str, SitePolicy]:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    defaults = {**DEFAULTS, **(raw.get("defaults") or {})}
    policies: dict[str, SitePolicy] = {}
    for name, site in (raw.get("sites") or {}).items():
        site = site or {}
        policies[name] = SitePolicy(
            name=name,
            enabled=bool(site.get("enabled", False)),
            domains=tuple(site.get("domains", [])),
            search_hints=tuple(site.get("search_hints", [name])),
            user_agent=site.get("user_agent", defaults["user_agent"]),
            min_interval_sec=float(site.get("min_interval_sec", defaults["min_interval_sec"])),
            max_requests_per_run=int(
                site.get("max_requests_per_run", defaults["max_requests_per_run"])
            ),
            request_timeout_sec=int(
                site.get("request_timeout_sec", defaults["request_timeout_sec"])
            ),
            respect_robots=bool(site.get("respect_robots", defaults["respect_robots"])),
            exclude_patterns=tuple(site.get("exclude_patterns", [])),
        )
    return policies
