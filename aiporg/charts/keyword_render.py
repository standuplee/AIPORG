"""키워드 조사 보고서 전용 차트 렌더러."""
from __future__ import annotations

import os

from ..models_keyword_report import KeywordReportModel


class KeywordChartRenderer:
    def __init__(self, out_dir: str):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)

    def render_all(self, model: KeywordReportModel) -> dict[str, str]:
        del model
        return {}
