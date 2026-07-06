"""개체명 인식 (PRD 7-③): 사람/기관/지역/정책/예산/사업명/기업명.

사전(lexicon)+패턴 기반 경량 NER. 운영 시 KoBERT-NER 등으로 교체 가능.
"""
from __future__ import annotations

import re
from collections import defaultdict

from ..models import Document

_PATTERNS = {
    "기관": re.compile(r"[가-힣]+(?:도청|도의회|시청|군청|국회|위원회|정부|부처|청)"),
    "지역": re.compile(r"[가-힣]{2,4}(?:특별시|광역시|도|시|군|구|읍|면)"),
    "예산": re.compile(r"\d[\d,\.]*\s*(?:조|억)(?:\s*\d+\s*(?:억|천억|천만))?\s*원?"),
    "기업명": re.compile(r"(?:삼성전자|SK하이닉스|현대자동차|LG[가-힣A-Za-z]*|[가-힣]+전자)"),
}


def extract(docs: list[Document], person_lexicon: list[str] | None = None) -> dict[str, list[str]]:
    persons = set(person_lexicon or [])
    found: dict[str, set[str]] = defaultdict(set)
    for d in docs:
        text = d.title + " " + d.body
        for label, pat in _PATTERNS.items():
            for m in pat.findall(text):
                found[label].add(m.strip())
        for p in persons:
            if p in text:
                found["사람"].add(p)
        d.entities = {k: sorted(v) for k, v in found.items()}
    return {k: sorted(v) for k, v in found.items()}
