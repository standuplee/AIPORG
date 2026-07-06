"""차트 렌더러."""
from __future__ import annotations

import logging
import os

from ..models import AnalysisResult

log = logging.getLogger(__name__)

# 공공기관 보고서 톤의 절제된 팔레트
PALETTE = {
    "primary": "#1f4e79", "positive": "#2e75b6", "neutral": "#a6a6a6",
    "negative": "#c00000", "accent": "#0070c0",
}
SENTIMENT_COLORS = {"긍정": "#2e75b6", "중립": "#bfbfbf", "부정": "#c00000", "혼재": "#ed7d31"}

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]


def _font_path() -> str | None:
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


class ChartRenderer:
    def __init__(self, out_dir: str):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self._setup_mpl()

    def _setup_mpl(self):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager

        fp = _font_path()
        if fp:
            try:
                font_manager.fontManager.addfont(fp)
                name = font_manager.FontProperties(fname=fp).get_name()
                plt.rcParams["font.family"] = name
            except Exception as e:  # noqa: BLE001
                log.warning("한국어 폰트 설정 실패: %s", e)
        plt.rcParams["axes.unicode_minus"] = False
        self.plt = plt

    def _save(self, fig, name: str) -> str:
        path = os.path.join(self.out_dir, name)
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        self.plt.close(fig)
        return path

    # ------------------------------------------------------------------ #
    def daily_volume(self, a: AnalysisResult, name="fig_2_1_volume.png") -> str | None:
        try:
            plt = self.plt
            days = list(a.daily_volume.keys())
            vals = list(a.daily_volume.values())
            xlabels = [d.split("-")[-1] for d in days]
            fig, ax = plt.subplots(figsize=(9, 3.2))
            ax.bar(range(len(vals)), vals, color=PALETTE["primary"], width=0.7)
            ax.plot(range(len(vals)), vals, color=PALETTE["negative"], lw=1.2, marker="o", ms=3)
            ax.set_xticks(range(0, len(vals), 2))
            ax.set_xticklabels(xlabels[::2], fontsize=8)
            ax.set_ylabel("언급량(건)")
            month = days[0].split("-")[1].lstrip("0") if days else ""
            ax.set_title(f"{month}월 일별 온라인 언급량 추이", fontsize=12, fontweight="bold")
            ax.grid(axis="y", alpha=0.3)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            return self._save(fig, name)
        except Exception as e:  # noqa: BLE001
            log.warning("daily_volume 차트 실패: %s", e)
            return None

    def channel_share(self, a: AnalysisResult, name="fig_2_1b_share.png") -> str | None:
        try:
            plt = self.plt
            items = sorted(a.channel_share.items(), key=lambda x: x[1], reverse=True)
            labels = [k for k, _ in items]
            vals = [v for _, v in items]
            fig, ax = plt.subplots(figsize=(5, 4))
            colors = plt.cm.Blues([0.4 + 0.5 * i / len(vals) for i in range(len(vals))][::-1])
            wedges, _, autotexts = ax.pie(
                vals, labels=labels, autopct=lambda p: f"{p:.0f}%",
                colors=colors, startangle=90, textprops={"fontsize": 9},
            )
            ax.set_title("채널별 언급 비중", fontsize=12, fontweight="bold")
            return self._save(fig, name)
        except Exception as e:  # noqa: BLE001
            log.warning("channel_share 차트 실패: %s", e)
            return None

    def channel_sentiment(self, a: AnalysisResult, name="fig_3_1_sentiment.png") -> str | None:
        try:
            plt = self.plt
            cs = a.channel_sentiments
            labels = [c.channel.short for c in cs]
            pos = [c.positive for c in cs]
            neu = [c.neutral for c in cs]
            neg = [c.negative for c in cs]
            fig, ax = plt.subplots(figsize=(8, 3.5))
            x = range(len(labels))
            ax.bar(x, pos, label="긍정", color=SENTIMENT_COLORS["긍정"])
            ax.bar(x, neu, bottom=pos, label="중립", color=SENTIMENT_COLORS["중립"])
            ax.bar(x, neg, bottom=[p + n for p, n in zip(pos, neu)],
                   label="부정", color=SENTIMENT_COLORS["부정"])
            ax.set_xticks(list(x))
            ax.set_xticklabels(labels)
            ax.set_ylabel("비율(%)")
            ax.set_title("채널별 감성 비율(%)", fontsize=12, fontweight="bold")
            ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12), frameon=False)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            return self._save(fig, name)
        except Exception as e:  # noqa: BLE001
            log.warning("channel_sentiment 차트 실패: %s", e)
            return None

    def channel_feature(self, a: AnalysisResult, name="fig_3_2_feature.png") -> str | None:
        try:
            plt = self.plt
            cs = sorted(a.channel_sentiments, key=lambda c: c.feature_volume, reverse=True)
            labels = [c.channel.short for c in cs]
            vals = [c.feature_volume for c in cs]
            fig, ax = plt.subplots(figsize=(7, 3.3))
            bars = ax.barh(labels[::-1], vals[::-1], color=PALETTE["accent"])
            ax.set_xlabel("언급량(건)")
            ax.set_title("채널별 여론 특징(언급량)", fontsize=12, fontweight="bold")
            for b, v in zip(bars, vals[::-1]):
                ax.text(b.get_width(), b.get_y() + b.get_height() / 2,
                        f" {v:,}", va="center", fontsize=8)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            return self._save(fig, name)
        except Exception as e:  # noqa: BLE001
            log.warning("channel_feature 차트 실패: %s", e)
            return None

    def wordcloud(self, a: AnalysisResult, name="fig_3_3_wordcloud.png") -> str | None:
        try:
            from wordcloud import WordCloud
            freq = {k.keyword: k.volume for k in a.related_keywords}
            wc = WordCloud(
                font_path=_font_path(), width=900, height=450, background_color="white",
                colormap="Blues", prefer_horizontal=0.9, max_words=40,
            ).generate_from_frequencies(freq)
            fig, ax = self.plt.subplots(figsize=(8, 4))
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            ax.set_title("충청남도 상위 연관 키워드", fontsize=12, fontweight="bold")
            return self._save(fig, name)
        except Exception as e:  # noqa: BLE001
            log.warning("wordcloud 차트 실패: %s", e)
            return None

    def keyword_network(self, a: AnalysisResult, name="fig_3_4_network.png") -> str | None:
        try:
            import networkx as nx
            plt = self.plt
            kws = a.related_keywords[:12]
            g = nx.Graph()
            center = self.__dict__.get("_subject", "충청남도")
            for k in kws:
                g.add_node(k.keyword, weight=k.volume)
                g.add_edge(center, k.keyword, weight=k.volume)
            # 상위 키워드 간 보조 연결
            for i in range(len(kws) - 1):
                if i % 2 == 0:
                    g.add_edge(kws[i].keyword, kws[i + 1].keyword, weight=1)
            pos = nx.spring_layout(g, seed=42, k=0.9)
            sizes = [g.nodes[n].get("weight", 3000) for n in g.nodes]
            sizes = [max(600, min(4000, s / 3)) for s in sizes]
            fig, ax = plt.subplots(figsize=(8, 5.5))
            nx.draw_networkx_edges(g, pos, alpha=0.3, ax=ax)
            nx.draw_networkx_nodes(g, pos, node_size=sizes, node_color=PALETTE["accent"],
                                   alpha=0.85, ax=ax)
            nx.draw_networkx_labels(g, pos, font_size=9,
                                    font_family=plt.rcParams["font.family"], ax=ax)
            ax.set_title("연관 키워드 네트워크", fontsize=12, fontweight="bold")
            ax.axis("off")
            return self._save(fig, name)
        except Exception as e:  # noqa: BLE001
            log.warning("keyword_network 차트 실패: %s", e)
            return None

    def job_eval_pie(self, a: AnalysisResult, name="fig_5_1_jobeval.png") -> str | None:
        try:
            je = a.job_evaluation
            if not je:
                return None
            plt = self.plt
            neutral = max(0.0, 100 - je.positive_pct - je.negative_pct)
            vals = [je.positive_pct, neutral, je.negative_pct]
            labels = [f"긍정 {je.positive_pct:.0f}%", f"중립 {neutral:.0f}%",
                      f"부정 {je.negative_pct:.0f}%"]
            colors = [SENTIMENT_COLORS["긍정"], SENTIMENT_COLORS["중립"], SENTIMENT_COLORS["부정"]]
            fig, ax = plt.subplots(figsize=(5, 4))
            ax.pie(vals, labels=labels, colors=colors, startangle=90,
                   wedgeprops={"width": 0.45}, textprops={"fontsize": 10})
            ax.set_title(f"{je.subject} 직무수행 평가", fontsize=12, fontweight="bold")
            return self._save(fig, name)
        except Exception as e:  # noqa: BLE001
            log.warning("job_eval_pie 차트 실패: %s", e)
            return None

    def core_issue_matrix(self, a: AnalysisResult, name="fig_4_1_core.png") -> str | None:
        try:
            plt = self.plt
            cores = a.core_keywords
            names = [c.name for c in cores]
            vols = [c.volume for c in cores]
            from ..models import Sentiment
            colors = [SENTIMENT_COLORS.get(c.sentiment.value, PALETTE["neutral"]) for c in cores]
            fig, ax = plt.subplots(figsize=(8, 3.5))
            bars = ax.bar(names, vols, color=colors)
            ax.set_ylabel("언급량(건)")
            ax.set_title("4대 핵심 이슈 언급량·감성", fontsize=12, fontweight="bold")
            for b, c in zip(bars, cores):
                ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                        f"{c.volume:,}\n({c.sentiment.value})", ha="center",
                        va="bottom", fontsize=8)
            ax.set_ylim(0, max(vols) * 1.25)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            return self._save(fig, name)
        except Exception as e:  # noqa: BLE001
            log.warning("core_issue_matrix 차트 실패: %s", e)
            return None

    def volume_dashboard(self, a, meta, name="fig_2_1_dashboard.png"):
        try:
            from .infographic import volume_dashboard
            return volume_dashboard(self.plt, a, meta, os.path.join(self.out_dir, name))
        except Exception as e:  # noqa: BLE001
            log.warning("volume_dashboard 실패: %s", e)
            return None

    def keyword_ranking(self, a, name="fig_3_3_ranking.png"):
        try:
            from .infographic import keyword_ranking
            return keyword_ranking(self.plt, a, os.path.join(self.out_dir, name))
        except Exception as e:  # noqa: BLE001
            log.warning("keyword_ranking 실패: %s", e)
            return None

    # ------------------------------------------------------------------ #
    # YouTube 채널 섹션 차트
    # ------------------------------------------------------------------ #
    def youtube_sentiment(self, report, name="fig_yt_sentiment.png") -> str | None:
        try:
            plt = self.plt
            cs = report.channel_sentiment
            parts = [("긍정", cs.positive), ("중립", cs.neutral),
                     ("부정", cs.negative), ("혼재", cs.mixed)]
            parts = [(k, v) for k, v in parts if v > 0]
            vals = [v for _, v in parts]
            labels = [f"{k} {v:.0f}%" for k, v in parts]
            colors = [SENTIMENT_COLORS.get(k, "#bfbfbf") for k, _ in parts]
            fig, ax = plt.subplots(figsize=(4.6, 3.8))
            ax.pie(vals, labels=labels, colors=colors, startangle=90,
                   wedgeprops={"width": 0.45}, textprops={"fontsize": 10})
            ax.set_title("유튜브 영상 댓글 감성 분포", fontsize=12, fontweight="bold")
            return self._save(fig, name)
        except Exception as e:  # noqa: BLE001
            log.warning("youtube_sentiment 실패: %s", e)
            return None

    def youtube_topics(self, report, name="fig_yt_topics.png") -> str | None:
        try:
            plt = self.plt
            tp = report.top_topics[:6]
            if not tp:
                return None
            labels = [t.topic for t in tp][::-1]
            vals = [t.ratio for t in tp][::-1]
            fig, ax = plt.subplots(figsize=(6.5, 3.2))
            ax.barh(labels, vals, color=PALETTE["accent"])
            ax.set_xlabel("영상 비중(%)")
            ax.set_title("유튜브 영상 토픽 분포", fontsize=12, fontweight="bold")
            for i, v in enumerate(vals):
                ax.text(v, i, f" {v:.0f}%", va="center", fontsize=8)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            return self._save(fig, name)
        except Exception as e:  # noqa: BLE001
            log.warning("youtube_topics 실패: %s", e)
            return None

    def youtube_keywords(self, report, name="fig_yt_keywords.png") -> str | None:
        try:
            plt = self.plt
            ks = report.top_keywords[:12]
            if not ks:
                return None
            labels = [k.keyword for k in ks][::-1]
            vals = [k.frequency for k in ks][::-1]
            fig, ax = plt.subplots(figsize=(6.5, 4.0))
            ax.barh(labels, vals, color=PALETTE["primary"])
            ax.set_xlabel("빈도")
            ax.set_title("유튜브 상위 키워드", fontsize=12, fontweight="bold")
            for i, v in enumerate(vals):
                ax.text(v, i, f" {v}", va="center", fontsize=8)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            return self._save(fig, name)
        except Exception as e:  # noqa: BLE001
            log.warning("youtube_keywords 실패: %s", e)
            return None

    def render_youtube(self, report) -> dict[str, str | None]:
        return {
            "yt_sentiment": self.youtube_sentiment(report),
            "yt_topics": self.youtube_topics(report),
            "yt_keywords": self.youtube_keywords(report),
        }

    def core_cards(self, a, name="fig_4_1_core_cards.png") -> str | None:
        try:
            from .infographic import core_keyword_cards
            if not any(c.summary or c.positive_point for c in a.core_keywords):
                return None      # 카드용 내용 없음 → 폴백(바 차트) 사용
            return core_keyword_cards(self.plt, a, os.path.join(self.out_dir, name))
        except Exception as e:  # noqa: BLE001
            log.warning("core_cards 실패: %s", e)
            return None

    def jobeval_dashboard(self, a, meta, name="fig_5_1_jobeval_dash.png") -> str | None:
        try:
            from .infographic import job_eval_dashboard
            if a.job_evaluation is None or not a.job_evaluation.comparison:
                return None      # 비교 데이터 없으면 폴백(도넛) 사용
            return job_eval_dashboard(self.plt, a, meta, os.path.join(self.out_dir, name))
        except Exception as e:  # noqa: BLE001
            log.warning("jobeval_dashboard 실패: %s", e)
            return None

    def render_all(self, a: AnalysisResult, subject: str = "충청남도", meta=None) -> dict[str, str | None]:
        self._subject = subject
        return {
            "volume": self.daily_volume(a),
            "volume_dash": self.volume_dashboard(a, meta) if meta else None,
            "share": self.channel_share(a),
            "sentiment": self.channel_sentiment(a),
            "feature": self.channel_feature(a),
            "wordcloud": self.wordcloud(a),
            "keyword_rank": self.keyword_ranking(a),
            "network": self.keyword_network(a),
            # 그림 4-1: 카드형 우선, 없으면 바 차트 폴백
            "core": self.core_cards(a) or self.core_issue_matrix(a),
            # 그림 5-1: 대시보드 우선, 없으면 도넛 폴백
            "jobeval": (self.jobeval_dashboard(a, meta) if meta else None)
                       or self.job_eval_pie(a),
        }
