from __future__ import annotations

from dataclasses import replace

from ..models import Document
from ..models_keyword_report import KeywordIssue


def rank_issues(
    docs: list[Document],
    issue_keywords: dict[str, list[str]] | None = None,
    top_n: int = 4,
) -> list[KeywordIssue]:
    issue_keywords = issue_keywords or {}
    ranked: list[tuple[float, KeywordIssue]] = []

    for issue_name, keywords in issue_keywords.items():
        matched = [doc for doc in docs if _matches_issue(doc, keywords)]
        if not matched:
            continue
        representative = max(matched, key=lambda doc: doc.views + doc.comments + doc.likes)
        issue = KeywordIssue(
            title=issue_name,
            subtitle=representative.title,
            body=representative.body or representative.title,
            evidence=[representative.url],
            source_notes=[representative.url],
            representative_documents=[doc.doc_id for doc in matched],
        )
        ranked.append((len(matched), issue))

    if not ranked and docs:
        representative = max(docs, key=lambda doc: doc.views + doc.comments + doc.likes)
        ranked.append(
            (
                1.0,
                KeywordIssue(
                    title=representative.title,
                    subtitle=representative.title,
                    body=representative.body or representative.title,
                    evidence=[representative.url],
                    source_notes=[representative.url],
                    representative_documents=[representative.doc_id],
                ),
            )
        )

    ranked.sort(key=lambda item: (-item[0], item[1].title))
    return [
        replace(issue, rank=index)
        for index, (_, issue) in enumerate(ranked[:top_n], start=1)
    ]


def _matches_issue(doc: Document, keywords: list[str]) -> bool:
    blob = f"{doc.title} {doc.body}"
    return any(keyword in blob for keyword in keywords)
