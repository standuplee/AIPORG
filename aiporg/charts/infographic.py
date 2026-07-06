"""인포그래픽형 차트 (참조 리포트 스타일 재현).

- volume_dashboard : 그림 2-1  KPI 카드 4종 + 주차별 추이 + 채널별 비중
- keyword_ranking  : 그림 3-3  상위 연관 키워드 랭킹 카드(2단)

원본 리포트의 시각 스타일(카드형 KPI, 감성 배지)을 재현한다.
"""
from __future__ import annotations

from matplotlib.patches import FancyBboxPatch, Rectangle

from ..models import AnalysisResult, ReportMeta, Sentiment

# 팔레트
NAVY = "#26365f"
BLUE = "#3f6098"
LBLUE = "#7ba7d0"
GREEN = "#33a08a"
CARD_BG = "#f6f9fc"
GRAY_TX = "#7a8699"
DARK_TX = "#2b2b2b"

CH_COLORS = {
    "뉴스기사": "#26365f", "커뮤니티": "#3f6098", "블로그": "#33a08a",
    "유튜브": "#e0863c", "공공RSS": "#5d6d7e",
    "X(트위터)": "#7ba7d0", "인스타그램": "#8e5aa6",   # (미수집; 폴백용)
}
SENT_COLOR = {
    Sentiment.POSITIVE: "#33a086", Sentiment.NEGATIVE: "#c0392b",
    Sentiment.NEUTRAL: "#7f8c9a", Sentiment.MIXED: "#e0893c",
}


def _round_box(ax, x, y, w, h, color, ec="none", lw=0, rad=0.02, z=1):
    box = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={rad}",
                         facecolor=color, edgecolor=ec, linewidth=lw, zorder=z,
                         mutation_aspect=1)
    ax.add_patch(box)
    return box


# --------------------------------------------------------------------------- #
def volume_dashboard(plt, a: AnalysisResult, meta: ReportMeta, out_path: str) -> str:
    fig = plt.figure(figsize=(12, 7))
    fig.patch.set_facecolor("white")

    # ---- 상단 KPI 카드 4종 ---- #
    bg = fig.add_axes([0, 0, 1, 1]); bg.axis("off")
    bg.set_xlim(0, 100); bg.set_ylim(0, 100)
    sv = a.subject_volumes
    keys = list(sv.keys())
    dojeong = keys[0] if keys else "충남도정"
    jisa = keys[1] if len(keys) > 1 else "충남지사"
    sc = a.subject_changes
    ov = a.overall_sentiment

    def chg(v):
        return f"+{v}" if v >= 0 else f"{v}"

    cards = [
        (f"총 언급량 ({meta.subject_name})", f"{a.total_volume:,}",
         f"건  (전월 대비 {chg(a.prev_change_pct)}%)", NAVY),
        (f"{dojeong} 언급량", f"{sv.get(dojeong,0):,}",
         f"건  (전월 대비 {chg(sc.get(dojeong,0))}%)", BLUE),
        (f"{jisa} 언급량", f"{sv.get(jisa,0):,}",
         f"건  (전월 대비 {chg(sc.get(jisa,0))}%)", LBLUE),
        ("긍정 여론 비율", f"{a.positive_ratio}",
         f"%  (부정 {ov.get('부정','-')}%, 중립 {ov.get('중립','-')}%)", GREEN),
    ]
    x0, w, gap, y0, h = 3.5, 22, 2.0, 74, 22
    for i, (title, val, sub, col) in enumerate(cards):
        x = x0 + i * (w + gap)
        _round_box(bg, x, y0, w, h, CARD_BG, ec="#e3e9f2", lw=1, rad=1.2)
        bg.add_patch(Rectangle((x, y0 + h - 2.4), w, 2.4, facecolor=col, zorder=2))
        bg.text(x + 1.6, y0 + h - 5.6, title, fontsize=10.5, color=GRAY_TX, va="center")
        bg.text(x + 1.6, y0 + h - 12.5, val, fontsize=25, color=NAVY,
                fontweight="bold", va="center")
        bg.text(x + 1.6, y0 + 3.2, sub, fontsize=8.5, color=GRAY_TX, va="center")

    # ---- 주차별 추이 (좌) ---- #
    ax = fig.add_axes([0.065, 0.10, 0.55, 0.50])
    weeks, series = _weekly_series(a, meta)
    labels = [dojeong, jisa]
    ax.plot(range(len(weeks)), series["총"], "-o", color=NAVY, lw=2.2, ms=6,
            label=meta.subject_name)
    ax.plot(range(len(weeks)), series[dojeong], "-o", color=BLUE, lw=2, ms=5, label=dojeong)
    ax.plot(range(len(weeks)), series[jisa], "-o", color=LBLUE, lw=2, ms=5, label=jisa)
    ax.set_xticks(range(len(weeks)))
    ax.set_xticklabels(weeks, fontsize=9, color=GRAY_TX)
    ax.set_title("주차별 온라인 언급량 추이 (건)", fontsize=12, color=NAVY, fontweight="bold")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3,
              frameon=False, fontsize=9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)

    # ---- 채널별 비중 (우) ---- #
    axb = fig.add_axes([0.70, 0.10, 0.27, 0.50]); axb.axis("off")
    axb.set_xlim(0, 100); axb.set_ylim(0, 100)
    axb.text(0, 96, "채널별 언급 비중", fontsize=12, color=NAVY, fontweight="bold")
    items = sorted(a.channel_share.items(), key=lambda x: x[1], reverse=True)
    n = len(items)
    top_y, row_h = 84, 84 / max(n, 1)
    maxv = max((v for _, v in items), default=1)
    for i, (ch, v) in enumerate(items):
        y = top_y - i * row_h
        col = CH_COLORS.get(ch, BLUE)
        axb.add_patch(Rectangle((2, y), 3, 3, facecolor=col))
        axb.text(7, y + 1.5, ch, fontsize=9.5, color=DARK_TX, va="center")
        bar_w = 34 * (v / maxv)
        axb.add_patch(Rectangle((48, y + 0.4), bar_w, 2.4, facecolor=col))
        axb.text(96, y + 1.5, f"{v:.0f}%", fontsize=9.5, color=DARK_TX,
                 va="center", ha="right", fontweight="bold")

    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
def core_keyword_cards(plt, a: AnalysisResult, out_path: str) -> str:
    """그림 4-1  4대 핵심 이슈 상세 카드 (2×2)."""
    cores = a.core_keywords[:4]
    if not cores:
        return out_path
    badge_colors = ["#3a5488", "#4a72b0", "#7a5aa0", "#4a9a7a"]
    fig = plt.figure(figsize=(12, 7.6))
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)

    col_x = [2.0, 51.0]
    card_w, card_h = 47.0, 44.0
    tops = [97.0, 50.0]
    for i, c in enumerate(cores):
        col, row = i // 2, i % 2
        x, top = col_x[col], tops[row]
        col_c = badge_colors[i]
        _round_box(ax, x, top - card_h, card_w, card_h, "#ffffff", ec="#dfe5ee",
                   lw=1, rad=0.7)
        ax.add_patch(Rectangle((x, top - 12), card_w, 12, facecolor="#eef2f7"))
        # 번호 배지
        ax.add_patch(Rectangle((x + 1.5, top - 11), 9, 10, facecolor=col_c))
        ax.text(x + 6, top - 6, f"{i+1:02d}", color="white", fontsize=14,
                fontweight="bold", ha="center", va="center")
        # 제목 + 건수
        ax.text(x + 12.5, top - 6, c.name, fontsize=13, color=DARK_TX,
                fontweight="bold", va="center")
        ax.text(x + card_w - 2, top - 6, f"{c.volume:,}건", fontsize=12,
                color=col_c, fontweight="bold", ha="right", va="center")
        # 요약
        ax.text(x + 3, top - 17, c.summary or c.analysis[:46], fontsize=9.6,
                color=DARK_TX, va="center")
        # ▲ 긍정 / ▼ 부정
        if c.positive_point:
            ax.text(x + 3, top - 24, "▲", fontsize=9, color="#2e8b6f", va="center")
            ax.text(x + 6, top - 24, c.positive_point, fontsize=8.7,
                    color="#2e6b57", va="center")
        if c.negative_point:
            ax.text(x + 3, top - 30, "▼", fontsize=9, color="#c0392b", va="center")
            ax.text(x + 6, top - 30, c.negative_point, fontsize=8.7,
                    color="#8f2e22", va="center")
        # 구분선 + 핵심어
        ax.plot([x + 3, x + card_w - 3], [top - 35, top - 35], color="#e2e8f1", lw=1)
        if c.keywords:
            ax.text(x + 3, top - 40, "핵심어: " + ", ".join(c.keywords), fontsize=8.3,
                    color=GRAY_TX, va="center", style="italic")

    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
def job_eval_dashboard(plt, a: AnalysisResult, meta: ReportMeta, out_path: str) -> str:
    """그림 5-1  직무수행 평가: 도넛 + 단체장 비교 + 긍/부정 원인."""
    je = a.job_evaluation
    if je is None:
        return out_path
    neutral = je.neutral_pct or max(0.0, 100 - je.positive_pct - je.negative_pct)
    sub_title = meta.subject_name
    if sub_title.endswith("도"):
        sub_title = sub_title[:-1] if sub_title == "충청남도" else sub_title
    title_name = "충남도지사"

    fig = plt.figure(figsize=(12, 7))
    fig.patch.set_facecolor("white")

    # 좌: 도넛
    axd = fig.add_axes([0.02, 0.40, 0.34, 0.52])
    vals = [je.positive_pct, je.negative_pct, neutral]
    labels = [f"{je.positive_pct:.0f}%", f"{je.negative_pct:.0f}%", f"{neutral:.0f}%"]
    colors = ["#2e9e86", "#c0503f", "#8a97a8"]
    axd.pie(vals, labels=labels, colors=colors, startangle=90, labeldistance=0.78,
            wedgeprops={"width": 0.42}, textprops={"fontsize": 12, "color": "white",
                                                    "fontweight": "bold",
                                                    "ha": "center", "va": "center"})
    axd.set_title(f"{title_name} 직무수행 평가", fontsize=12, fontweight="bold")
    axd.legend(["긍정 평가", "부정 평가", "모름·무응답"], loc="upper center",
               bbox_to_anchor=(0.5, -0.02), ncol=3, frameon=False, fontsize=9)

    # 우: 광역단체장 비교 barh
    if je.comparison:
        axb = fig.add_axes([0.46, 0.42, 0.5, 0.50])
        names = list(je.comparison.keys())
        vals2 = list(je.comparison.values())
        y = list(range(len(names)))
        bar_colors = []
        for nm in names:
            if nm == je.highlight_region:
                bar_colors.append("#e0a53c")
            elif nm == "전국평균":
                bar_colors.append("#26365f")
            else:
                bar_colors.append("#5b8ac4")
        axb.barh(y, vals2, color=bar_colors, height=0.62)
        axb.set_yticks(y); axb.set_yticklabels(names, fontsize=9.5)
        axb.invert_yaxis()
        axb.set_xlim(0, 70)
        axb.set_title("광역자치단체장 긍정평가 비교 (%)", fontsize=12, fontweight="bold")
        for yi, v in zip(y, vals2):
            axb.text(v + 0.8, yi, f"{v:.0f}", va="center", fontsize=9)
        for s in ("top", "right", "left"):
            axb.spines[s].set_visible(False)
        axb.tick_params(length=0)

    # 하단: 긍정/부정 원인
    bg = fig.add_axes([0, 0, 1, 1]); bg.axis("off")
    bg.set_xlim(0, 100); bg.set_ylim(0, 100)
    bg.text(3, 30, "긍정 평가 주요 원인", fontsize=11.5, color="#2e9e86", fontweight="bold")
    for i, r in enumerate(je.positive_reasons[:3]):
        yy = 24 - i * 6
        bg.add_patch(Rectangle((3, yy - 0.6), 2, 2.6, facecolor="#2e9e86"))
        bg.text(6.5, yy + 0.7, r, fontsize=9.2, color=DARK_TX, va="center")
    bg.text(52, 30, "부정 평가 주요 원인", fontsize=11.5, color="#c0503f", fontweight="bold")
    for i, r in enumerate(je.negative_reasons[:3]):
        yy = 24 - i * 6
        bg.add_patch(Rectangle((52, yy - 0.6), 2, 2.6, facecolor="#c0503f"))
        bg.text(55.5, yy + 0.7, r, fontsize=9.2, color=DARK_TX, va="center")

    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def _weekly_series(a: AnalysisResult, meta: ReportMeta):
    """daily_volume → 5주차 집계 + 대상 비율 시리즈."""
    import calendar
    weekly = [0] * 6
    for k, v in a.daily_volume.items():
        try:
            day = int(k.split("-")[-1])
        except Exception:
            continue
        weekly[min((day - 1) // 7, 5)] += v
    weekly = [w for w in weekly if True]
    # 마지막 주 병합(6주째가 있으면 5주째에 합산)
    if len(weekly) == 6 and weekly[5]:
        weekly[4] += weekly[5]
    weekly = weekly[:5]
    total = a.total_volume or sum(weekly) or 1
    sv = a.subject_volumes
    keys = list(sv.keys())
    dj, js = (keys + ["충남도정", "충남지사"])[:2]
    r_dj = sv.get(dj, 0) / total
    r_js = sv.get(js, 0) / total
    series = {
        "총": [round(w) for w in weekly],
        dj: [round(w * r_dj) for w in weekly],
        js: [round(w * r_js) for w in weekly],
    }
    # 주차 라벨 (월 마지막 일은 분석기간 종료일 기준)
    last = meta.period_end.day
    ranges = [(1, 7), (8, 14), (15, 21), (22, 28), (29, last)]
    m = meta.month
    labels = [f"{i+1}주차\n({m}.{s}~{e})" for i, (s, e) in enumerate(ranges)]
    return labels, series


# --------------------------------------------------------------------------- #
def keyword_ranking(plt, a: AnalysisResult, out_path: str, top_n: int = 12) -> str:
    kws = a.related_keywords[:top_n]
    if not kws:
        return out_path
    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)

    rows = (len(kws) + 1) // 2
    maxv = max(k.volume for k in kws) or 1
    col_x = [2, 51]        # 좌/우 컬럼 시작 x
    col_w = 47
    top_y, row_h = 96, 96 / rows

    for idx, k in enumerate(kws):
        col = idx // rows if False else (0 if idx < rows else 1)
        row = idx if idx < rows else idx - rows
        x = col_x[col]
        y = top_y - (row + 1) * row_h + row_h * 0.12
        ch = row_h * 0.76
        rank = idx + 1
        # 카드 배경
        _round_box(ax, x, y, col_w, ch, "#ffffff", ec="#e6ebf2", lw=1, rad=0.9)
        # 랭크 박스
        rc = "#d4a017" if rank <= 3 else "#2c3e50"
        ax.add_patch(Rectangle((x, y), ch, ch, facecolor=rc))
        ax.text(x + ch / 2, y + ch / 2, str(rank), color="white", fontsize=14,
                fontweight="bold", ha="center", va="center")
        # 키워드명
        tx = x + ch + 2
        ax.text(tx, y + ch * 0.66, k.keyword, fontsize=11.5, color=DARK_TX,
                fontweight="bold", va="center")
        # 값 바
        scol = SENT_COLOR.get(k.sentiment, "#7f8c9a")
        bar_max = col_w - (ch + 2) - 12
        bw = bar_max * (k.volume / maxv)
        ax.add_patch(Rectangle((tx, y + ch * 0.16), bar_max, ch * 0.22,
                               facecolor="#eef1f5"))
        ax.add_patch(Rectangle((tx, y + ch * 0.16), max(bw, 1.2), ch * 0.22,
                               facecolor=scol))
        ax.text(tx + max(bw, 1.2) + 1, y + ch * 0.27, f"{k.volume:,}건",
                fontsize=8.5, color=GRAY_TX, va="center")
        # 감성 배지
        bx, bw2 = x + col_w - 11, 9.5
        _round_box(ax, bx, y + ch * 0.32, bw2, ch * 0.42, scol, rad=0.5, z=3)
        ax.text(bx + bw2 / 2, y + ch * 0.53, k.sentiment.value, color="white",
                fontsize=9.5, fontweight="bold", ha="center", va="center", zorder=4)

    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path
