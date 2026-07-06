"""Markdown 보고서 생성기."""
from __future__ import annotations

import os

from ..llm.narrator import Narrator
from ..models import ReportModel


def write_markdown(model: ReportModel, narrator: Narrator, charts: dict, out_path: str) -> str:
    m, a, n = model.meta, model.analysis, narrator
    L: list[str] = []
    L.append(f"# {m.report_title}\n")
    L.append(f"> {m.year}년 {m.month}월 여론분석 컨설팅 리포트 · 수집도구 {m.tool_name}\n")

    L.append("## Ⅰ. 분석 개요\n")
    for s in n.overview_purpose():
        L.append(f"- {s}")
    L.append("\n**[표 1-2] 키워드 수집 체계**\n")
    L.append("| 구분 | 내용 |\n|---|---|")
    for g, kws in m.keywords.items():
        L.append(f"| {g} | {', '.join(kws)} |")

    L.append(f"\n## Ⅱ. {m.month}월 주요 이슈 동향\n")
    L.append("### 01 온라인 언급량 개요\n")
    for s in n.volume_overview():
        L.append(f"- {s}")
    L.append("\n### 02 핵심 이슈 TOP10\n")
    for s in n.top_issues_overview():
        L.append(f"- {s}")
    L.append("\n| 순위 | 구분 | 이슈 | 건수 | 증감 | 반응 |\n|---|---|---|---|---|---|")
    for i in a.top_issues:
        sign = f"+{i.change_pct:.0f}%" if i.change_pct >= 0 else f"{i.change_pct:.0f}%"
        L.append(f"| {i.rank} | {i.category} | {i.title} | {i.volume:,}건 | {sign} | {i.sentiment.value} |")

    L.append("\n## Ⅲ. 온라인 여론 동향\n")
    for s in n.channel_sentiment():
        L.append(f"- {s}")
    L.append("")
    for s in n.related_keywords():
        L.append(f"- {s}")
    L.append("\n**[표 3-1] 특이 온라인 동향**\n")
    L.append("| 구분 | 내용 |\n|---|---|")
    for t in a.special_trends:
        L.append(f"| {t.title} | {t.detail.replace(chr(10), ' ')} |")
    for s in n.special_trends_summary():
        L.append(f"\n- {s}")

    L.append(f"\n## Ⅳ. {m.subject_name} 핵심 키워드 분석\n")
    for s in n.core_keywords_intro() + n.core_keywords_detail():
        L.append(f"- {s}")

    L.append(f"\n## Ⅴ. {m.leader_title} 직무수행 평가\n")
    for s in n.job_evaluation():
        L.append(f"- {s}")

    L.append("\n## Ⅵ. 종합 시사점 및 제언\n")
    L.append("| No. | 시사점 | 대응 제언 |\n|---|---|---|")
    for idx, imp in enumerate(a.implications, 1):
        L.append(f"| {idx:02d} | {imp.topic} — {imp.headline} | {imp.response} |")
    L.append("")
    for s in n.implications_conclusion():
        L.append(f"- {s}")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return out_path
