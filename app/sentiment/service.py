"""Deterministic Korean sentiment/stance lexicon classifier.

No network access, no LLM call (the project's established architecture
keeps LLM calls in the Narrative layer only -- see HANDOFF.md). Adapted
from 1.0's dictionary-based classifier (``aiporg/analyze/sentiment.py``),
which was never ported to 2.0.

Sentiment (general positive/negative/neutral/mixed tone) and stance
(policy support/oppose) are deliberately two separate lexicons and two
separate classification calls -- requirements doc §4.3: "정책 찬반과 일반
감성도 별도 개념으로 다룬다". Praising how a policy was delivered is
positive *sentiment*; opposing the policy itself is a *stance* -- the two
can disagree (e.g. praising the rollout of a policy you oppose).

This is a small controlled-vocabulary baseline, not a trained model --
expect it to call plenty of real text NEUTRAL/NOT_APPLICABLE when no
lexicon word appears. An LLM-based classifier (1.0 has one,
``aiporg/llm/sentiment_llm.py``, batching through the Narrative-layer
provider with a lexicon fallback) is a possible future upgrade, not
something this module does.
"""

from app.core.enums import SentimentLabel, StanceLabel

_POSITIVE_SENTIMENT_WORDS = frozenset({
    "유치", "성과", "기대", "확대", "호재", "개선", "성공", "발전",
    "지원", "혜택", "최대", "역대", "강화", "활성화", "우수", "선도",
    "투자", "일자리", "증설", "확충", "호평", "쾌거", "낭보",
})
_NEGATIVE_SENTIMENT_WORDS = frozenset({
    "우려", "논란", "갈등", "부족", "불발", "무산", "비판", "지적",
    "불확실", "미흡", "졸속", "폐지", "축소", "지연", "위기", "혼란",
    "실패", "피해", "사고", "논쟁", "불안", "참사",
})
_SUPPORT_STANCE_WORDS = frozenset({
    "찬성", "지지", "환영", "공감", "동의", "협력", "호응",
})
_OPPOSE_STANCE_WORDS = frozenset({
    "반대", "반발", "규탄", "철회", "저지", "비난", "항의",
})


class SentimentService:
    """Classify a single piece of grounded text (a fact claim, an evidence
    excerpt) into a sentiment label and, separately, a stance label."""

    def classify_sentiment(self, text: str) -> SentimentLabel:
        positive = sum(1 for word in _POSITIVE_SENTIMENT_WORDS if word in text)
        negative = sum(1 for word in _NEGATIVE_SENTIMENT_WORDS if word in text)
        if positive == 0 and negative == 0:
            return SentimentLabel.NEUTRAL
        if positive > 0 and negative > 0 and abs(positive - negative) <= 1:
            return SentimentLabel.MIXED
        if positive > negative:
            return SentimentLabel.POSITIVE
        if negative > positive:
            return SentimentLabel.NEGATIVE
        return SentimentLabel.NEUTRAL

    def classify_stance(self, text: str) -> StanceLabel:
        support = sum(1 for word in _SUPPORT_STANCE_WORDS if word in text)
        oppose = sum(1 for word in _OPPOSE_STANCE_WORDS if word in text)
        if support == 0 and oppose == 0:
            return StanceLabel.NOT_APPLICABLE
        if support > 0 and oppose > 0 and abs(support - oppose) <= 1:
            return StanceLabel.MIXED
        if support > oppose:
            return StanceLabel.SUPPORT
        if oppose > support:
            return StanceLabel.OPPOSE
        return StanceLabel.NEUTRAL
