"""HTML 보고서 생성기 (웹 미리보기용, 차트 임베드)."""
from __future__ import annotations

import base64
import os

from ..llm.narrator import Narrator
from ..models import ReportModel

CSS = """
body{font-family:'맑은 고딕','Malgun Gothic',AppleGothic,sans-serif;color:#262626;
max-width:900px;margin:0 auto;padding:40px;line-height:1.7}
h1{color:#1f4e79;border-bottom:3px solid #1f4e79;padding-bottom:8px}
h2{color:#1f4e79;margin-top:36px;border-left:6px solid #0070c0;padding-left:10px}
h3{color:#0070c0}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px}
th{background:#1f4e79;color:#fff;padding:8px;border:1px solid #ccc}
td{padding:8px;border:1px solid #ccc}
td:first-child{background:#deeaf1;text-align:center;font-weight:bold}
.foot{color:#888;font-size:12px;text-align:right}
img{max-width:100%;display:block;margin:12px auto}
li{margin:4px 0}
"""


def _img(path):
    if not path or not os.path.exists(path):
        return ""
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    return f'<img src="data:image/png;base64,{b64}"/>'


def write_html(model: ReportModel, narrator: Narrator, charts: dict, out_path: str) -> str:
    m, a, n = model.meta, model.analysis, narrator
    h: list[str] = [f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
                    f"<title>{m.report_title}</title><style>{CSS}</style></head><body>"]
    h.append(f"<h1>{m.report_title}</h1>")
    h.append(f"<p class='foot'>{m.year}년 {m.month}월 여론분석 컨설팅 · 수집도구 {m.tool_name}</p>")

    h.append("<h2>Ⅰ. 분석 개요</h2><ul>")
    h += [f"<li>{s}</li>" for s in n.overview_purpose()]
    h.append("</ul><table><tr><th>구분</th><th>내용</th></tr>")
    for g, kws in m.keywords.items():
        h.append(f"<tr><td>{g}</td><td>{', '.join(kws)}</td></tr>")
    h.append("</table>")

    h.append(f"<h2>Ⅱ. {m.month}월 주요 이슈 동향</h2><h3>01 온라인 언급량 개요</h3><ul>")
    h += [f"<li>{s}</li>" for s in n.volume_overview()]
    h.append("</ul>" + _img(charts.get("volume")) + _img(charts.get("share")))
    h.append("<h3>02 핵심 이슈 TOP10</h3><ul>")
    h += [f"<li>{s}</li>" for s in n.top_issues_overview()]
    h.append("</ul><table><tr><th>순위</th><th>구분</th><th>이슈</th><th>건수</th>"
             "<th>증감</th><th>반응</th></tr>")
    for i in a.top_issues:
        sign = f"+{i.change_pct:.0f}%" if i.change_pct >= 0 else f"{i.change_pct:.0f}%"
        h.append(f"<tr><td>{i.rank}</td><td>{i.category}</td><td style='text-align:left'>"
                 f"{i.title}</td><td>{i.volume:,}건</td><td>{sign}</td><td>{i.sentiment.value}</td></tr>")
    h.append("</table>")

    h.append("<h2>Ⅲ. 온라인 여론 동향</h2>")
    h.append(_img(charts.get("sentiment")))
    h.append("<ul>" + "".join(f"<li>{s}</li>" for s in n.channel_sentiment()) + "</ul>")
    h.append(_img(charts.get("feature")))
    h.append("<ul>" + "".join(f"<li>{s}</li>" for s in n.related_keywords()) + "</ul>")
    h.append(_img(charts.get("wordcloud")) + _img(charts.get("network")))
    h.append("<table><tr><th>구분</th><th>내용</th></tr>")
    for t in a.special_trends:
        h.append(f"<tr><td>{t.title}</td><td>{t.detail}</td></tr>")
    h.append("</table><ul>" + "".join(f"<li>{s}</li>" for s in n.special_trends_summary()) + "</ul>")

    h.append(f"<h2>Ⅳ. {m.subject_name} 핵심 키워드 분석</h2>")
    h.append(_img(charts.get("core")))
    h.append("<ul>" + "".join(f"<li>{s}</li>"
             for s in n.core_keywords_intro() + n.core_keywords_detail()) + "</ul>")

    h.append(f"<h2>Ⅴ. {m.leader_title} 직무수행 평가</h2>")
    h.append(_img(charts.get("jobeval")))
    h.append("<ul>" + "".join(f"<li>{s}</li>" for s in n.job_evaluation()) + "</ul>")

    h.append("<h2>Ⅵ. 종합 시사점 및 제언</h2><table><tr><th>No.</th><th>시사점</th>"
             "<th>대응 제언</th></tr>")
    for idx, imp in enumerate(a.implications, 1):
        h.append(f"<tr><td>{idx:02d}</td><td>{imp.topic} — {imp.headline}</td>"
                 f"<td style='text-align:left'>{imp.body}<br><b>▷ 대응 :</b> {imp.response}</td></tr>")
    h.append("</table><ul>" + "".join(f"<li>{s}</li>" for s in n.implications_conclusion()) + "</ul>")

    h.append("</body></html>")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("".join(h))
    return out_path
