from __future__ import annotations

from ..models_keyword_report import KeywordIssue, SentimentDriver


def build_recommendations(
    issues: list[KeywordIssue],
    positive_drivers: list[SentimentDriver],
    negative_drivers: list[SentimentDriver],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    implications: list[dict[str, str]] = []
    channel_actions: list[dict[str, str]] = []

    for issue in issues[:3]:
        implications.append(
            {
                "topic": issue.title,
                "headline": f"{issue.title} 대응 필요",
                "body": issue.body or issue.subtitle or issue.title,
            }
        )

    for driver in negative_drivers[:2]:
        channel_actions.append(
            {
                "channel": "온라인 채널",
                "action": f"{driver.title} 관련 설명과 대응 메시지 강화",
            }
        )

    for driver in positive_drivers[:1]:
        channel_actions.append(
            {
                "channel": "온라인 채널",
                "action": f"{driver.title} 성과 메시지 확산",
            }
        )

    return implications, channel_actions
