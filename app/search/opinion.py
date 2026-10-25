"""Opinion Research V1: neutral queries -> blog/cafe corpus -> qualitative Qwen analysis.

Search API hits are a sample, not the whole online opinion, so no percentages are produced.
"""

import json
import re
from collections import Counter
from enum import Enum
from itertools import zip_longest
from typing import Literal

from pydantic import Field

from app.analytics.service import _extract_keyword_tokens
from app.research.query.regions import REGION_ALIASES
from app.research.query_expansion import QwenQueryExpansionService
from app.schemas.common import SchemaBase
from app.schemas.research import IssueDecomposition, IssueInput
from app.search.documents import FactResearchResult
from app.search.period import classify_period
from app.search.schemas import PeriodStatus, SearchResult
from app.search.service import SearchService
from app.search.signals import noise_flags

MAX_QUERIES = 5
PER_QUERY_LIMIT = 15
MAX_ANALYZED = 40
MIN_CHANNEL_POSTS = 3
MIN_TOPIC_SOURCES = 2  # a topic needs at least this many distinct posts behind it
MAX_TOPICS = 8
MAX_TOPIC_SHARE = 0.8  # a topic nearly every post mentions is the issue itself, not a topic
SAME_SOURCES = 0.8  # Jaccard overlap of source sets above which two topics count as duplicates
SNIPPET_CHARS = 200
NUM_CTX = 16384
LIMITATIONS = "네이버·다음 검색 API가 반환한 블로그·카페 글 표본이며 전체 온라인 여론이 아니다. 비율은 산출하지 않았다."


class OverallSentiment(str, Enum):
    POSITIVE = "긍정 우세"
    POSITIVE_NEUTRAL = "긍정·중립 혼재"
    NEGATIVE = "우려·비판 우세"
    SPLIT = "긍정·우려 혼재"
    UNKNOWN = "뚜렷한 여론 방향 판단 어려움"


class ReactionTone(str, Enum):
    POSITIVE = "POSITIVE"
    CONCERN = "CONCERN"
    CRITICISM = "CRITICISM"
    REQUEST = "REQUEST"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"


class ReactionTheme(SchemaBase):
    theme: str
    tone: ReactionTone
    summary: str
    source_result_ids: list[str]  # posts that actually express this reaction


class ChannelInsight(SchemaBase):
    channel: str
    sample_size: int  # posts with a reaction in this channel
    main_reactions: list[str]  # theme names backed by this channel's posts
    sentiment: OverallSentiment


class OpinionAnalysis(SchemaBase):
    """What Qwen produces for the reaction layer: themes and a summary, never an overall verdict."""

    reaction_themes: list[ReactionTheme]
    analysis_summary: str


class DiscussionTopic(SchemaBase):
    """What the collected posts keep talking about (facts, policy and news included). Says nothing about sentiment."""

    topic_id: str = ""  # assigned in code
    topic: str
    summary: str
    source_result_ids: list[str]


class TopicExtraction(SchemaBase):
    topics: list[DiscussionTopic]


class DiscussionPost(SchemaBase):
    result_id: str
    channel: str
    title: str
    url: str
    snippet: str
    content_type: str


ContentType = Literal["REACTION", "POLICY_INFORMATION", "NEWS_REPOST", "UNRELATED"]


class OpinionFilterResult(SchemaBase):
    result_id: str
    relevant: bool  # is about this issue in this region
    relevance_reason: str | None = None  # one sentence a reviewer can check: why this post is about the issue
    content_type: ContentType
    reaction_evidence: str | None = None  # verbatim phrase from the post; required for REACTION


class EvidenceCheck(SchemaBase):
    result_id: str
    is_actual_reaction: bool
    reason: str


class EvidenceCheckBatch(SchemaBase):
    checks: list[EvidenceCheck]


class ReactionPost(SchemaBase):
    """A post that passed every gate, with the phrase that proves it carries a reaction."""

    result_id: str
    channel: str
    title: str
    reaction_evidence: str
    verification_reason: str
    url: str
    snippet: str
    relevance_reason: str | None = None


class OpinionCandidates(SchemaBase):
    """Stage 1 output: everything a reviewer needs to approve or strike each reaction before themes are built."""

    issue: str
    queries: list[str]
    corpus_size: int
    relevant_count: int
    filtered_out: dict[str, int]
    exclude_keywords: list[str]
    candidates: list[ReactionPost]
    discussion_posts: list[DiscussionPost] = Field(default_factory=list)  # every relevant post, reactions or not
    topics: list[DiscussionTopic] = Field(default_factory=list)


class OpinionFilterBatch(SchemaBase):
    results: list[OpinionFilterResult]


class KeywordCount(SchemaBase):
    keyword: str
    doc_count: int


class OpinionResearchResult(OpinionAnalysis):
    key_topics: list[str]  # names of the discussion topics the reviewer kept
    discussion_topics: list[DiscussionTopic]
    discussion_size: int  # relevant posts the discussion layer drew on
    overall_sentiment: OverallSentiment  # last-step summary computed in code from the themes
    channel_insights: list[ChannelInsight]
    issue: str
    queries: list[str]
    corpus_size: int  # hits that passed period/term filters
    relevant_count: int
    reaction_count: int  # posts with verified reaction evidence; the only ones analysed
    reactions: list[ReactionPost]
    channel_counts: dict[str, int]
    filtered_out: dict[str, int]
    keywords: list[KeywordCount]
    limitations: str = LIMITATIONS


FILTER_BATCH = 10
MIN_OPINION_POSTS = 3
INSUFFICIENT = "분석 가능한 온라인 반응이 부족함"
INSUFFICIENT_DETAIL = "관련 검색 결과에서는 정책 및 행정조치를 전달하는 게시물이 주로 확인됐으며, 해당 정책에 대한 명시적인 평가·찬반·요구 등의 온라인 반응은 충분히 확인되지 않았다."
UNCLEAR = "뚜렷한 여론 방향 판단 어려움"

FILTER_PROMPT = """
당신은 온라인 글 선별기다. 각 글의 제목과 요약만 보고 판정한다.

relevant: 입력된 지역(region)의 이 이슈(issue) 자체를 다루는 글인가?
relevance_reason: relevant 판정의 이유를 한 문장으로. 이슈와 같은 단어가 있다는 이유만으로 relevant로 보지 않는다.
 - 다른 지역·해외 사례, 일반 기후·환경 논의, 이슈의 정책과 직접 관련 없는 글은 relevant=false.

content_type (하나만):
 - REACTION: 이 이슈·정책에 대해 작성자 또는 인용된 제3자가 평가, 기대, 우려, 비판, 요구, 체감, 경험, 문제 제기를
   명시적으로 표현했다.
 - POLICY_INFORMATION: 정책 내용, 행정조치, 사업 내용, 정책 목표를 설명한다. 도지사·도청·담당부서가 자기 정책을
   설명하는 발언("강화하겠다", "구축하겠다", "총력 대응하겠다")도 여기에 속한다.
 - NEWS_REPOST: 기사·보도자료·뉴스 내용을 사실상 그대로 전하거나 요약하며 작성자의 평가가 없다.
 - UNRELATED: 이 지역·정책·이슈 자체와 관련이 없다.

reaction_evidence: content_type이 REACTION일 때만, 제목 또는 요약에서 반응이 드러난 문장·구절을 글자 그대로 복사한다.
 - 바꿔 쓰거나 요약하거나 새로 만들지 않는다. 그런 구절이 없으면 REACTION으로 판정하지 말고 null로 둔다.
 - 나쁜 예) 원문 "AI와 드론을 활용해 폭염 대응을 강화한다" → evidence "AI·드론 활용에 대한 기대가 있다" (금지: 원문에 없음)
 - 좋은 예) 원문 "AI·드론 활용은 현장 대응에 도움이 될 것으로 기대한다" → evidence로 그 구절을 그대로 복사

REACTION 최종 검증 (reaction_evidence를 쓰기 전에 반드시 확인):
 이 문장은 분석 대상 정책·사업을 추진하는 당사자(지자체, 기업, 담당자)가 자신의 정책·사업·행동·목표·계획을 설명하는 문장인가?
 - YES → REACTION이 아니다(POLICY_INFORMATION). 당사자가 "필요하다", "강화해야 한다", "중요하다", "막아야 한다"라고 말해도
   자기 정책의 필요성과 목표를 설명하는 발언이면 온라인 반응이 아니다.
 - NO → 시민·주민·이해관계자·전문가 등 외부 인물이 그 정책을 평가·기대·우려·비판·요구하거나 체감·경험을 말했을 때만 REACTION이다.
 예) 지사 "현장 대응을 강화하겠다" → 정책 설명. 주민 "쉼터가 멀어 이용하기 어렵다" → 반응. 전문가 "현재 대책만으로는 부족하다" → 반응.
 예) 기업 "아산에 단계적으로 투자하겠다" → 계획. 지역 상인 "투자로 지역경제가 살아날 것으로 기대한다" → 반응.
 투자 규모나 사실만 언급한 글은 반응이 아니다.

정책이 어떤 목표를 갖고 있다는 사실을, 사람들이 그 목표를 요구하거나 기대한다는 뜻으로 바꾸지 않는다.
판단이 애매하면 REACTION이 아니다. 입력의 모든 result_id에 대해 정확히 하나씩 반환한다.
"""

VERIFY_PROMPT = """
각 항목은 온라인 글에서 '반응'이라고 뽑은 근거 구절(evidence)이다. 월간 보고서를 쓰는 사람이 자료를 읽으며 하듯 판단한다.

is_actual_reaction = true: 정책·사업을 추진하는 당사자(지자체, 기업, 담당 부서)가 아닌 외부 인물(시민, 주민, 업계, 노동계,
 전문가, 시민단체, 의원 등)이 그 정책·사안을 평가·기대·우려·비판·요구하거나 체감·경험을 말한 구절.
is_actual_reaction = false: 법안 통과·계획 발표 같은 사실 서술, 정책 당사자의 설명·입장·요구, 뉴스 제목, 배경 설명.

예) "특별법이 국회 본회의를 통과했다" → false (현황 사실)
예) "충남도, 기금 별도계정·국고보조 확대 요구" → false (정책 당사자의 입장)
예) "취지는 환영하나 탈석탄의 원칙은 빠졌다" → true (외부 성명의 비판)
예) "정의로운 전환 지원센터를 조속히 설립해야" → 발언자가 외부 이해관계자이면 true, 정책 당사자이면 false
reason에 한 문장으로 이유를 쓴다. 입력의 모든 result_id에 대해 정확히 하나씩 반환한다.
"""

OPINION_PROMPT = """
당신은 월간 이슈 보고서를 위한 온라인 반응 분석 보조자다.
주어진 글들(각각 result_id가 있다)에서 이 이슈에 대해 글쓴이들이 실제로 표현한 반응의 논점(theme)을 뽑는다.

규칙:
1. 글에 실제로 쓰인 반응만 논점으로 만든다. 정책 내용을 반응으로 바꾸지 않는다.
   "AI·드론을 활용한다"는 정책 내용이지 반응이 아니다. "AI·드론 활용이 효과적일 것 같다"는 기대다.
2. 각 글에는 reaction_evidence가 있다. 논점은 그 evidence에 나타난 반응으로만 만든다.
   각 논점에는 theme(짧은 이름), tone(POSITIVE=기대·긍정 평가, CONCERN=우려, CRITICISM=비판, REQUEST=요구,
   NEUTRAL=평가 없는 관심, MIXED=양면), summary(한 문장), source_result_ids(그 반응이 있는 글의 id)를 쓴다.
3. source_result_ids에는 입력에 있는 id만 쓰고, 그 글에 그 반응이 글쓴이의 표현으로 실제로 있어야 한다.
   기관의 발표·정책 설명·보도 내용만 있는 글은 근거로 쓰지 않는다. 정책이 목표를 갖고 있다는 사실을
   "사람들이 그 목표를 요구·기대한다"로 바꾸지 않는다. 직접 뒷받침되지 않으면 그 논점을 만들지 않는다.
   뒷받침되는 논점이 없으면 reaction_themes를 빈 목록으로 둔다.
4. 퍼센트, 건수 같은 숫자를 쓰지 않는다. 전체 분위기를 판정하지 않는다.
5. analysis_summary는 논점들을 한두 문장으로 요약한다. 논점에 없는 내용을 쓰지 않는다.
"""

TOPIC_PROMPT = """
당신은 월간 이슈 보고서를 위한 논점 정리 보조자다. 이 이슈에 대해 수집된 온라인 글(기사 전재, 정책 소개, 보도자료, 블로그 포함)에서
**반복적으로 다뤄지는 논점**을 뽑는다. 논점은 "무엇이 많이 이야기되는가"이며, 사람들의 기대·우려·평가가 아니다.

규칙:
1. 논점은 짧은 이름(topic)과 한 문장 설명(summary)으로 쓴다. 예) "노동자 고용 전환", "폐쇄지역 경제 충격", "발전공기업 통합본사 유치".
2. source_result_ids에는 그 논점을 실제로 다루는 글의 id를 모두 넣는다. 서로 다른 글 2건 이상이 다루는 논점만 만든다.
3. 사실·정책·기사 내용도 논점이 될 수 있다. 단, summary는 반드시 "이 글들은 ~를 다룬다" 또는 "~가 논의된다" 꼴로 쓴다.
   무엇이 마련되었다·통과되었다·해결된다처럼 일어난 일로 단정하지 않고, 시민·지역사회·업계의 기대, 우려, 평가, 요구, 반응이
   있다고도 쓰지 않는다.
4. 논점끼리 서로 다른 주제여야 한다. 같은 글 묶음을 이름만 바꿔 여러 논점으로 만들지 않는다.
5. 이슈 이름 자체는 논점이 아니다. 입력에 없는 사실과 숫자를 만들지 않는다.
6. 논점은 최대 8개.
"""


def build_queries(issue: IssueInput, fact: FactResearchResult | None = None) -> list[str]:
    """Neutral queries only: the issue wording plus region/place names, never 기대/우려 words."""
    aliases = REGION_ALIASES.get(issue.region, [issue.region])
    queries = [issue.issue, *(f"{a} {issue.issue}" for a in aliases)]
    places = [p for p in (fact.locations if fact else []) if p not in aliases and len(p) <= 8]
    queries += [f"{issue.issue} {p}" for p in places[:2]]
    return list(dict.fromkeys(queries))[:MAX_QUERIES]


# Words that are frequent in any news-like text and say nothing about a specific issue.
GENERIC_KEYWORDS = frozenset({"규모", "계획", "발표", "지원", "통과", "마련", "대응", "추진", "관련", "이번", "통해", "위해", "국회", "구축", "확대"})
def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def key_terms(issue: IssueInput, decomposition: IssueDecomposition | None = None) -> list[str]:
    actions = {_norm(a) for a in (decomposition.actions if decomposition else [])}
    return [t for t in issue.issue.split() if _norm(t) not in actions] or issue.issue.split()


async def collect_corpus(
    search: SearchService, issue: IssueInput, queries: list[str], terms: list[str]
) -> tuple[list[SearchResult], dict[str, int]]:
    seen, hits = set(), []
    for q in queries:  # sequential: stays gentle on the free API quotas
        for r in await search.search_opinion(q, PER_QUERY_LIMIT):
            if r.result_id not in seen:
                seen.add(r.result_id)
                hits.append(r)
    dropped: Counter[str] = Counter()
    kept = []
    wanted = [_norm(t) for t in terms]
    for r in hits:
        text = _norm(f"{r.title} {r.snippet}")
        if classify_period(r, issue.start_date, issue.end_date) is PeriodStatus.OUT_OF_PERIOD:
            dropped["out_of_period"] += 1
        elif noise_flags(r):
            dropped["structural_noise"] += 1
        elif not any(t in text for t in wanted):
            dropped["no_issue_term"] += 1
        else:
            kept.append(r)  # undated hits stay: blogs/cafes often lack a reliable date
    return kept, dict(dropped)


def top_keywords(corpus: list[SearchResult], exclude: list[str], n: int = 15) -> list[KeywordCount]:
    """Document frequency of noun phrases, minus the issue's own words and region names."""
    banned = [_norm(t) for t in exclude if _norm(t)]
    counts: Counter[str] = Counter()
    for r in corpus:
        counts.update({k for k in _extract_keyword_tokens(f"{r.title} {r.snippet}") if k not in GENERIC_KEYWORDS and not any(b in _norm(k) or _norm(k) in b for b in banned)})
    return [KeywordCount(keyword=k, doc_count=c) for k, c in counts.most_common(n)]


async def _ask_all(qwen, prompt: str, items: list[SearchResult], build, schema, results_of, batch: int) -> dict:
    """Run Qwen over items in batches; an 8B model sometimes skips items, so re-ask once for the missing ones."""
    answers: dict = {}
    for i in range(0, len(items), batch):
        todo = items[i : i + batch]
        for _ in range(2):
            out = await qwen.chat(prompt, json.dumps(build(todo), ensure_ascii=False), schema)
            wanted = {r.result_id for r in todo}
            answers.update({a.result_id: a for a in results_of(out) if a.result_id in wanted})
            todo = [r for r in todo if r.result_id not in answers]
            if not todo:
                break
        if todo:
            raise ValueError(f"Qwen did not answer: {[r.result_id for r in todo]}")
    return answers


async def filter_posts(
    qwen: QwenQueryExpansionService, issue: IssueInput, corpus: list[SearchResult]
) -> dict[str, OpinionFilterResult]:
    return await _ask_all(
        qwen, FILTER_PROMPT, corpus,
        lambda todo: {"region": issue.region, "issue": issue.issue,
                      "posts": [{"result_id": r.result_id, "channel": r.channel.value, "title": r.title, "summary": r.snippet[:SNIPPET_CHARS]} for r in todo]},
        OpinionFilterBatch, lambda out: out.results, FILTER_BATCH,
    )


async def verify_reactions(
    qwen: QwenQueryExpansionService, issue: IssueInput, candidates: list[SearchResult], evidence: dict[str, str]
) -> dict[str, EvidenceCheck]:
    """Second, narrower look at just the quoted phrase: external reaction, or policy/fact statement?"""
    return await _ask_all(
        qwen, VERIFY_PROMPT, candidates,
        lambda todo: {"region": issue.region, "issue": issue.issue,
                      "items": [{"result_id": r.result_id, "title": r.title, "evidence": evidence[r.result_id]} for r in todo]},
        EvidenceCheckBatch, lambda out: out.checks, FILTER_BATCH,
    )


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def check_reaction(post: SearchResult, verdict: OpinionFilterResult) -> str:
    """Returns "ok" or the reason this post is not a reaction candidate (the evidence must be a real quote)."""
    if not verdict.relevant or verdict.content_type == "UNRELATED":
        return "unrelated"
    if verdict.content_type == "POLICY_INFORMATION":
        return "policy_information"
    if verdict.content_type == "NEWS_REPOST":
        return "news_repost"
    evidence = (verdict.reaction_evidence or "").strip()
    if not evidence:
        return "evidence_missing"
    if _squash(evidence) not in _squash(f"{post.title} {post.snippet[:SNIPPET_CHARS]}"):
        return "evidence_not_in_text"  # Qwen wrote its own sentence instead of quoting
    return "ok"


def _sample(posts: list[ReactionPost]) -> list[ReactionPost]:
    """Round-robin across channels so a chatty channel cannot crowd out the others."""
    by_channel: dict[str, list[ReactionPost]] = {}
    for r in posts:
        by_channel.setdefault(r.channel, []).append(r)
    mixed = [r for group in zip_longest(*by_channel.values()) for r in group if r]
    return mixed[:MAX_ANALYZED]


def summarize_tone(themes: list[ReactionTheme]) -> OverallSentiment:
    """Last-step summary. Counts distinct posts per direction; requests/neutral/mixed add no direction."""
    pos = {i for t in themes if t.tone is ReactionTone.POSITIVE for i in t.source_result_ids}
    con = {i for t in themes if t.tone in (ReactionTone.CONCERN, ReactionTone.CRITICISM) for i in t.source_result_ids}
    if len(pos | con) < MIN_CHANNEL_POSTS:
        return OverallSentiment.UNKNOWN
    share = len(pos) / (len(pos) + len(con))
    if share >= 0.75:
        return OverallSentiment.POSITIVE
    if share <= 0.25:
        return OverallSentiment.NEGATIVE
    return OverallSentiment.SPLIT


def channel_insights(posts: list[ReactionPost], themes: list[ReactionTheme]) -> list[ChannelInsight]:
    """Built in code from theme sources, so a channel claim always rests on counted posts."""
    out = []
    for channel in dict.fromkeys(r.channel for r in posts):
        ids = {r.result_id for r in posts if r.channel == channel}
        own = [t.model_copy(update={"source_result_ids": [i for i in t.source_result_ids if i in ids]}) for t in themes]
        own = [t for t in own if t.source_result_ids]
        enough = len(ids) >= MIN_CHANNEL_POSTS
        out.append(ChannelInsight(
            channel=channel, sample_size=len(ids),
            main_reactions=[t.theme for t in own] if enough and own else ["표본 부족으로 채널 경향 판단 어려움"],
            sentiment=summarize_tone(own) if enough else OverallSentiment.UNKNOWN,
        ))
    return out


async def extract_topics(
    qwen: QwenQueryExpansionService, issue: IssueInput, posts: list[DiscussionPost]
) -> list[DiscussionTopic]:
    """Discussion layer. Qwen names the topics; code decides which survive by counting the distinct posts behind each."""
    if len(posts) < MIN_TOPIC_SOURCES:
        return []
    by_channel: dict[str, list[DiscussionPost]] = {}
    for p in posts:
        by_channel.setdefault(p.channel, []).append(p)
    sample = [p for group in zip_longest(*by_channel.values()) for p in group if p][:MAX_ANALYZED]
    shown = {p.result_id for p in sample}
    payload = json.dumps(
        {"region": issue.region, "issue": issue.issue,
         "posts": [{"result_id": p.result_id, "channel": p.channel, "title": p.title, "summary": p.snippet} for p in sample]},
        ensure_ascii=False,
    )
    out: TopicExtraction = await qwen.chat(TOPIC_PROMPT, payload, TopicExtraction, num_ctx=NUM_CTX)
    text = {p.result_id: _norm(f"{p.title} {p.snippet}") for p in posts}
    topics, seen = [], set()
    for t in out.topics:
        # Qwen tends to paste one long id list under every topic, so support is re-derived in code: a post backs a
        # topic only if it actually contains most of the topic name's words.
        words = [w for w in _extract_keyword_tokens(t.topic) if w not in GENERIC_KEYWORDS]
        need = max(1, len(words) // 2)
        ids = [i for i in dict.fromkeys(t.source_result_ids) if i in shown and sum(_norm(w) in text[i] for w in words) >= need] if words else []
        topics.append((t, ids))
    kept: list[DiscussionTopic] = []
    for t, ids in sorted(topics, key=lambda x: -len(x[1])):
        if len(ids) < MIN_TOPIC_SOURCES or not t.topic.strip() or _norm(t.topic) in seen or _norm(t.topic) == _norm(issue.issue):
            continue
        if len(sample) >= 10 and len(ids) / len(sample) > MAX_TOPIC_SHARE:
            continue
        # Several topics that cite almost the same posts are one topic with different names; keep the first.
        if any(len(set(ids) & set(k.source_result_ids)) / len(set(ids) | set(k.source_result_ids)) >= SAME_SOURCES for k in kept):
            continue
        seen.add(_norm(t.topic))
        kept.append(t.model_copy(update={"source_result_ids": ids}))
    return [t.model_copy(update={"topic_id": f"T{n}"}) for n, t in enumerate(kept[:MAX_TOPICS], 1)]


async def find_reaction_candidates(
    qwen: QwenQueryExpansionService,
    issue: IssueInput,
    queries: list[str],
    corpus: list[SearchResult],
    filtered_out: dict[str, int],
    exclude_keywords: list[str],
) -> OpinionCandidates:
    """Stage 1: Qwen's first pass, the quote check in code, and Qwen's second look at the quoted phrase."""
    if not corpus:
        raise ValueError("empty opinion corpus")
    verdicts = await filter_posts(qwen, issue, corpus)
    reasons = {r.result_id: check_reaction(r, verdicts[r.result_id]) for r in corpus}
    quoted = [r for r in corpus if reasons[r.result_id] == "ok"]
    evidence = {r.result_id: verdicts[r.result_id].reaction_evidence.strip() for r in quoted}
    checks = await verify_reactions(qwen, issue, quoted, evidence) if quoted else {}
    for r in quoted:
        if not checks[r.result_id].is_actual_reaction:
            reasons[r.result_id] = "verification_rejected"
    discussion = [
        DiscussionPost(result_id=r.result_id, channel=r.channel.value, title=r.title, url=r.original_url or r.url,
                       snippet=r.snippet[:SNIPPET_CHARS], content_type=verdicts[r.result_id].content_type)
        for r in corpus if reasons[r.result_id] != "unrelated"
    ]
    topics = await extract_topics(qwen, issue, discussion)
    return OpinionCandidates(
        issue=issue.issue, queries=queries, corpus_size=len(corpus),
        relevant_count=sum(1 for r in corpus if reasons[r.result_id] != "unrelated"),
        filtered_out={**filtered_out, **Counter(v for v in reasons.values() if v != "ok")},
        exclude_keywords=exclude_keywords, discussion_posts=discussion, topics=topics,
        candidates=[
            ReactionPost(result_id=r.result_id, channel=r.channel.value, title=r.title, reaction_evidence=evidence[r.result_id],
                         verification_reason=checks[r.result_id].reason, url=r.original_url or r.url, snippet=r.snippet[:SNIPPET_CHARS],
                         relevance_reason=verdicts[r.result_id].relevance_reason)
            for r in quoted if reasons[r.result_id] == "ok"
        ],
    )


async def analyze_reactions(
    qwen: QwenQueryExpansionService,
    issue: IssueInput,
    found: OpinionCandidates,
    approved_ids: set[str] | None = None,
    approved_topic_ids: set[str] | None = None,
) -> OpinionResearchResult:
    """Stage 2: themes from the approved reactions, plus the kept discussion topics. None approves everything."""
    reacting = [r for r in found.candidates if approved_ids is None or r.result_id in approved_ids]
    topics = [t for t in found.topics if approved_topic_ids is None or t.topic_id in approved_topic_ids]
    excluded = Counter(found.filtered_out)
    excluded["reviewer_rejected"] = len(found.candidates) - len(reacting)
    base = dict(
        issue=issue.issue, queries=found.queries, corpus_size=found.corpus_size, relevant_count=found.relevant_count,
        reaction_count=len(reacting), channel_counts=dict(Counter(r.channel for r in reacting)), reactions=reacting,
        filtered_out={k: v for k, v in excluded.items() if v},
        # keywords describe what is discussed, so they come from every relevant post, not only from reactions
        keywords=top_keywords(found.discussion_posts or reacting, [*issue.issue.split(), issue.region, *found.exclude_keywords]),
        key_topics=[t.topic for t in topics], discussion_topics=topics, discussion_size=len(found.discussion_posts),
    )
    if len(reacting) < MIN_OPINION_POSTS:
        # Say so instead of inventing reactions from too few posts.
        relay = excluded["policy_information"] + excluded["news_repost"]
        return OpinionResearchResult(
            overall_sentiment=OverallSentiment.UNKNOWN, reaction_themes=[],
            channel_insights=channel_insights(reacting, []),
            analysis_summary=f"{INSUFFICIENT}. {INSUFFICIENT_DETAIL}" if relay else INSUFFICIENT, **base,
        )
    sample = _sample(reacting)
    shown = {r.result_id for r in sample}
    payload = json.dumps(
        {
            "region": issue.region, "issue": issue.issue,
            "posts": [{"result_id": r.result_id, "channel": r.channel, "title": r.title,
                       "summary": r.snippet, "reaction_evidence": r.reaction_evidence} for r in sample],
        },
        ensure_ascii=False,
    )
    a: OpinionAnalysis = await qwen.chat(OPINION_PROMPT, payload, OpinionAnalysis, num_ctx=NUM_CTX)
    # A theme counts only through posts Qwen was shown; with no valid source it is dropped.
    themes = []
    for t in a.reaction_themes:
        ids = list(dict.fromkeys(i for i in t.source_result_ids if i in shown))
        if ids and t.theme.strip() and t.summary.strip():
            themes.append(t.model_copy(update={"source_result_ids": ids}))
    overall = summarize_tone(themes)
    return OpinionResearchResult(
        reaction_themes=themes,
        analysis_summary=(a.analysis_summary if overall is not OverallSentiment.UNKNOWN else f"{UNCLEAR}. {a.analysis_summary}") if themes else UNCLEAR,
        overall_sentiment=overall,
        channel_insights=channel_insights(reacting, themes),
        **base,
    )


async def analyze_opinion(
    qwen: QwenQueryExpansionService,
    issue: IssueInput,
    queries: list[str],
    corpus: list[SearchResult],
    filtered_out: dict[str, int],
    exclude_keywords: list[str],
) -> OpinionResearchResult:
    """Both stages back to back, with no human review (every candidate approved)."""
    found = await find_reaction_candidates(qwen, issue, queries, corpus, filtered_out, exclude_keywords)
    return await analyze_reactions(qwen, issue, found)
