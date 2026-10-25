import asyncio
from datetime import date, datetime, timezone

from app.schemas.research import IssueDecomposition, IssueInput
from app.search import base
from app.search.documents import FactResearchResult
from app.search.naver import NaverSearchProvider
from app.search.opinion import (
    EvidenceCheck, EvidenceCheckBatch, OpinionAnalysis, OpinionFilterBatch, OpinionFilterResult, OverallSentiment, ReactionTheme, ReactionTone,
    analyze_opinion, analyze_reactions, approved_from_review, build_queries, channel_insights, check_reaction, collect_corpus, filter_posts, find_reaction_candidates, key_terms, review_rows, summarize_tone, top_keywords,
)
from app.search.schemas import SearchChannel as C
from app.search.schemas import SearchProvider, SearchResult

ISSUE = IssueInput(region="충청남도", start_date=date(2026, 9, 1), end_date=date(2026, 9, 30), issue="삼성디스플레이 67조 투자")


def _hit(i, title, snippet="", channel=C.BLOG, published=None, url=None):
    return SearchResult(provider=SearchProvider.DAUM, channel=channel, query="q", sort="accuracy", title=title,
                        snippet=snippet, url=url or f"https://blog.example/{i}", published_at=published, rank=1)


def test_queries_are_neutral_and_use_region_aliases_and_places():
    fact = FactResearchResult(summary="", key_facts=[], organizations=[], persons=[], locations=["충청남도", "아산시", "아산디스플레이시티2 일반산업단지"],
                              timeline=[], uncertainties=[], missing_information=[])
    qs = build_queries(ISSUE, fact)
    assert qs == ["삼성디스플레이 67조 투자", "충청남도 삼성디스플레이 67조 투자", "충남 삼성디스플레이 67조 투자", "삼성디스플레이 67조 투자 아산시"]
    assert not any(w in q for q in qs for w in ("기대", "우려", "문제", "논란", "호재"))


def test_naver_blog_postdate_becomes_kst_datetime(monkeypatch):
    monkeypatch.setattr(base.SearchProviderBase, "_get", staticmethod(
        lambda url, **kw: {"items": [{"title": "t", "description": "d", "link": "l", "postdate": "20260901"}]}))
    r = asyncio.run(NaverSearchProvider("i", "s").search("q", C.BLOG))[0]
    assert (r.published_at.year, r.published_at.day, r.published_at.utcoffset().seconds // 3600) == (2026, 1, 9)


def test_corpus_filters_period_noise_and_unrelated_but_keeps_undated():
    ok = _hit(1, "삼성디스플레이 아산 투자 후기", "동네가 들썩", published=datetime(2026, 9, 3, tzinfo=timezone.utc))
    undated = _hit(2, "삼성디스플레이 소식", "아산")
    old = _hit(3, "삼성디스플레이 투자", published=datetime(2026, 1, 3, tzinfo=timezone.utc))
    off = _hit(4, "맛집 추천", "삼성 이야기 없음")
    noisy = _hit(5, "삼성디스플레이", url="https://blog.example/list?page=2")
    dupe = _hit(1, "삼성디스플레이 아산 투자 후기")

    class FakeSearch:
        async def search_opinion(self, query, limit):
            return [ok, undated, old, off, noisy, dupe]

    kept, dropped = asyncio.run(collect_corpus(FakeSearch(), ISSUE, ["a", "b"], ["삼성디스플레이"]))
    assert [r.title for r in kept] == [ok.title, undated.title]
    assert dropped == {"out_of_period": 1, "no_issue_term": 1, "structural_noise": 1}


def test_key_terms_skip_generic_actions_and_keywords_exclude_obvious_terms():
    d = IssueDecomposition(subjects=[], actions=["투자"], amounts=[], locations=[], organizations=[], policies=[],
                           explicit_in_input=[], unknowns=[])
    assert key_terms(ISSUE, d) == ["삼성디스플레이", "67조"]
    corpus = [_hit(1, "삼성디스플레이 아산 협력업체 기대"), _hit(2, "아산 협력업체 전력 인프라")]
    kws = {k.keyword: k.doc_count for k in top_keywords(corpus, ["삼성디스플레이", "충청남도"])}
    assert kws["아산"] == 2 and kws["협력업체"] == 2 and "삼성디스플레이" not in kws


WORRY = "예산이 걱정된다"


class _FilterQwen:
    """Title keywords steer the verdict so each gate can be tested."""

    def __init__(self, analysis_for=None):
        self.analysis_for = analysis_for
        self.payload = None

    async def chat(self, system, user, schema, *, num_ctx=None):
        import json

        data = json.loads(user)
        if schema is EvidenceCheckBatch:  # second look at the quoted phrase only
            return EvidenceCheckBatch(checks=[
                EvidenceCheck(result_id=i["result_id"], is_actual_reaction="구호" not in i["title"], reason="r") for i in data["items"]])
        if schema is not OpinionFilterBatch:
            self.payload = data
            return self.analysis_for(data["posts"])
        out = []
        for p in data["posts"]:
            t = p["title"]
            if "무관" in t:
                v = ("UNRELATED", None, False)
            elif "정책" in t:
                v = ("POLICY_INFORMATION", None, True)
            elif "재게시" in t:
                v = ("NEWS_REPOST", None, True)
            elif "근거없음" in t:
                v = ("REACTION", None, True)
            elif "지어냄" in t:
                v = ("REACTION", "기술 활용에 대한 기대가 있다", True)      # not in the text
            elif "구호" in t:
                v = ("REACTION", WORRY, True)                              # quoted correctly, but the verifier says policy
            else:
                v = ("REACTION", WORRY, True)
            out.append(OpinionFilterResult(result_id=p["result_id"], relevant=v[2], content_type=v[0], reaction_evidence=v[1]))
        return OpinionFilterBatch(results=out)


def _theme(tone, ids, name="쉼터 확대"):
    return ReactionTheme(theme=name, tone=tone, summary="s", source_result_ids=ids)


def _post(i, label, channel=C.BLOG):
    return _hit(i, f"삼성디스플레이 {label} {i} {WORRY} 현장 대응력을 강화한다", channel=channel)


def test_each_gate_blocks_what_it_should_and_only_verified_reactions_reach_theme_extraction():
    reactions = [_post(i, "의견") for i in range(6)]
    others = ([_post(10, "정책"), _post(11, "재게시"), _post(12, "근거없음"), _post(13, "지어냄"), _post(14, "구호")]
              + [_post(20 + i, "무관") for i in range(2)])
    ids = [h.result_id for h in reactions]
    # the slogan post: Qwen's first pass quotes it faithfully, the narrower second look rejects it
    slogan = _hit(14, f"삼성디스플레이 구호 14 {WORRY}")
    others[4] = slogan

    def analysis(posts):
        return OpinionAnalysis(
            key_topics=["아산", "삼성디스플레이 67조 투자"], analysis_summary="s",
            reaction_themes=[_theme(ReactionTone.POSITIVE, ids[:4]),
                             _theme(ReactionTone.CONCERN, [ids[4], "ghost"], "전력 부족"),
                             _theme(ReactionTone.CONCERN, [slogan.result_id, "ghost"], "근거없음")])

    qwen = _FilterQwen(analysis)
    out = asyncio.run(analyze_opinion(qwen, ISSUE, ["q"], reactions + others, {"out_of_period": 2}, []))
    assert [p["result_id"] for p in qwen.payload["posts"]] == ids
    assert all(p["reaction_evidence"] == WORRY for p in qwen.payload["posts"])
    assert (out.corpus_size, out.relevant_count, out.reaction_count) == (13, 11, 6)
    assert out.filtered_out == {
        "out_of_period": 2, "policy_information": 1, "news_repost": 1, "evidence_missing": 1,
        "evidence_not_in_text": 1, "verification_rejected": 1, "unrelated": 2}
    assert [r.result_id for r in out.reactions] == ids and out.reactions[0].reaction_evidence == WORRY
    assert out.reactions[0].verification_reason == "r"
    assert [(t.theme, t.source_result_ids) for t in out.reaction_themes] == [("쉼터 확대", ids[:4]), ("전력 부족", [ids[4]])]
    assert out.key_topics == ["아산"]
    assert out.overall_sentiment is OverallSentiment.POSITIVE
    assert [(c.channel, c.sample_size) for c in out.channel_insights] == [("BLOG", 6)]


def test_too_few_verified_reactions_says_so_and_names_the_policy_relay():
    corpus = [_post(i, "의견") for i in range(2)] + [_post(10 + i, "정책") for i in range(5)] + [_post(20, "재게시")]
    qwen = _FilterQwen()  # analysis_for=None would crash if theme extraction were attempted
    out = asyncio.run(analyze_opinion(qwen, ISSUE, ["q"], corpus, {}, []))
    assert out.overall_sentiment is OverallSentiment.UNKNOWN
    assert out.analysis_summary.startswith("분석 가능한 온라인 반응이 부족함") and "정책 및 행정조치를 전달하는 게시물" in out.analysis_summary
    assert out.reaction_themes == [] and out.reaction_count == 2 and qwen.payload is None
    assert out.channel_insights[0].main_reactions == ["표본 부족으로 채널 경향 판단 어려움"]


def test_check_reaction_only_requires_a_real_quote_no_word_lists():
    post = _hit(1, "제목", f"어르신들에게 {WORRY}")
    mk = lambda **kw: OpinionFilterResult(result_id="x", relevant=True, content_type="REACTION", **kw)
    assert check_reaction(post, mk(reaction_evidence=WORRY)) == "ok"
    assert check_reaction(post, mk(reaction_evidence="예산이   걱정된다")) == "ok"  # whitespace-insensitive
    assert check_reaction(post, mk(reaction_evidence=None)) == "evidence_missing"
    assert check_reaction(post, mk(reaction_evidence="없는 문장")) == "evidence_not_in_text"
    # no vocabulary gate any more: whether this phrase is a reaction is the second Qwen look's job
    assert check_reaction(_hit(2, "t", "회의가 열렸다"), mk(reaction_evidence="회의가 열렸다")) == "ok"


def test_overall_tone_is_a_last_step_summary_and_channels_need_enough_posts():
    t = lambda tone, ids: _theme(tone, ids)
    assert summarize_tone([t(ReactionTone.REQUEST, ["a", "b", "c", "d"])]) is OverallSentiment.UNKNOWN  # requests give no direction
    assert summarize_tone([t(ReactionTone.POSITIVE, ["a", "b", "c"]), t(ReactionTone.CRITICISM, ["d"])]) is OverallSentiment.POSITIVE
    assert summarize_tone([t(ReactionTone.POSITIVE, ["a", "b", "c"]), t(ReactionTone.CONCERN, ["d"])]) is OverallSentiment.POSITIVE
    assert summarize_tone([t(ReactionTone.POSITIVE, ["a", "b"]), t(ReactionTone.CONCERN, ["c", "d"])]) is OverallSentiment.SPLIT
    assert summarize_tone([t(ReactionTone.CONCERN, ["a", "b", "c"])]) is OverallSentiment.NEGATIVE
    assert summarize_tone([t(ReactionTone.NEUTRAL, ["a", "b", "c", "d"])]) is OverallSentiment.UNKNOWN
    assert summarize_tone([t(ReactionTone.POSITIVE, ["a", "b"])]) is OverallSentiment.UNKNOWN  # fewer than 3 posts

    blog = [_hit(i, f"블로그 {i}") for i in range(4)]
    cafe = [_hit(10 + i, f"카페 {i}", channel=C.CAFE) for i in range(2)]
    themes = [_theme(ReactionTone.CONCERN, [h.result_id for h in blog + cafe])]
    got = {c.channel: c for c in channel_insights(blog + cafe, themes)}
    assert got["BLOG"].sample_size == 4 and got["BLOG"].sentiment is OverallSentiment.NEGATIVE and got["BLOG"].main_reactions == ["쉼터 확대"]
    assert got["CAFE"].sample_size == 2 and got["CAFE"].sentiment is OverallSentiment.UNKNOWN  # 2 posts: no channel verdict


def test_filter_retries_skipped_posts_and_fails_loudly_otherwise():
    import pytest

    corpus = [_hit(i, f"삼성디스플레이 의견 {i}") for i in range(3)]

    class Skips(_FilterQwen):
        calls = 0

        async def chat(self, system, user, schema, *, num_ctx=None):
            Skips.calls += 1
            out = await super().chat(system, user, schema, num_ctx=num_ctx)
            return OpinionFilterBatch(results=out.results[:1]) if Skips.calls == 1 else out

    assert len(asyncio.run(filter_posts(Skips(), ISSUE, corpus))) == 3 and Skips.calls == 2

    class Never(_FilterQwen):
        async def chat(self, system, user, schema, *, num_ctx=None):
            return OpinionFilterBatch(results=[])

    with pytest.raises(ValueError, match="did not answer"):
        asyncio.run(filter_posts(Never(), ISSUE, corpus))


def test_human_review_between_the_two_stages_decides_what_becomes_a_theme():
    corpus = [_post(i, "의견") for i in range(6)]
    ids = [h.result_id for h in corpus]
    qwen = _FilterQwen(lambda posts: OpinionAnalysis(
        key_topics=["아산"], analysis_summary="s", reaction_themes=[_theme(ReactionTone.CONCERN, [p["result_id"] for p in posts])]))
    found = asyncio.run(find_reaction_candidates(qwen, ISSUE, ["q"], corpus, {}, []))
    assert [c.result_id for c in found.candidates] == ids and found.candidates[0].url.startswith("https:")
    assert qwen.payload is None  # stage 1 never builds themes

    rows = review_rows(found)
    assert all(r["approved"] for r in rows) and rows[0]["reaction_evidence"] == WORRY
    for r in rows[:4]:
        r["approved"] = False                      # the reviewer strikes four of the six
    approved = approved_from_review(rows)
    out = asyncio.run(analyze_reactions(qwen, ISSUE, found, approved))
    assert out.reaction_count == 2 and out.filtered_out["reviewer_rejected"] == 4
    assert out.analysis_summary.startswith("분석 가능한 온라인 반응이 부족함") and qwen.payload is None  # 2 < minimum: no invented themes

    out = asyncio.run(analyze_reactions(qwen, ISSUE, found, set(ids[:5])))
    assert [p["result_id"] for p in qwen.payload["posts"]] == ids[:5] and out.reaction_themes[0].source_result_ids == ids[:5]
