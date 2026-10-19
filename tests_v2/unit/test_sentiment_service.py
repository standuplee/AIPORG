from app.core.enums import SentimentLabel, StanceLabel
from app.sentiment.service import SentimentService


def test_classify_sentiment_detects_positive_and_negative_tone() -> None:
    service = SentimentService()
    assert service.classify_sentiment("일자리 확대와 투자 유치 성과를 냈다.") is SentimentLabel.POSITIVE
    assert service.classify_sentiment("사업 지연과 혼란으로 비판이 쏟아졌다.") is SentimentLabel.NEGATIVE


def test_classify_sentiment_defaults_to_neutral_without_lexicon_words() -> None:
    service = SentimentService()
    assert service.classify_sentiment("충청남도가 정책을 발표했다.") is SentimentLabel.NEUTRAL


def test_classify_sentiment_returns_mixed_when_balanced() -> None:
    service = SentimentService()
    # one positive, one negative word, evenly matched -> mixed, not forced
    # to pick a side
    assert service.classify_sentiment("성과도 있었지만 비판도 있었다.") is SentimentLabel.MIXED


def test_classify_stance_is_a_separate_axis_from_sentiment() -> None:
    service = SentimentService()
    # praising how a policy was delivered is positive *sentiment*; opposing
    # the policy itself is a *stance* -- the two must not be conflated
    text = "행정통합에 반대하지만 소통 방식은 성과로 평가된다."
    assert service.classify_sentiment(text) is SentimentLabel.POSITIVE
    assert service.classify_stance(text) is StanceLabel.OPPOSE


def test_classify_stance_defaults_to_not_applicable_without_stance_words() -> None:
    service = SentimentService()
    assert service.classify_stance("집중호우로 주택 침수 피해가 발생했다.") is StanceLabel.NOT_APPLICABLE


def test_classify_stance_detects_support_and_mixed() -> None:
    service = SentimentService()
    assert service.classify_stance("주민들이 환영하며 지지 의사를 밝혔다.") is StanceLabel.SUPPORT
    assert service.classify_stance("일부는 지지했고 다른 일부는 반대했다.") is StanceLabel.MIXED
