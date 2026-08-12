"""키워드 조사 보고서 section 렌더링 헬퍼."""
from __future__ import annotations

from .keyword_layout import empty_state_text


def fallback_text(has_data: bool) -> str:
    return "" if has_data else empty_state_text()
