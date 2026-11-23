"""Run one issue end to end (plan -> fact search -> read -> synthesize -> opinion) and save the review session and the corpus.

Usage: ./.venv/bin/python -m app.research.runner --name coal --region 충청남도 --start 2026-08-01 --end 2026-08-31 --issue "석탄화력폐지지역 특별법"
Needs the search API keys in the environment and a local Ollama with qwen3:8b. With all 11 questions this takes a long time on a local model.
"""

import argparse
import asyncio
from datetime import date
from pathlib import Path

from app.research.corpus import IssueCorpus, build_corpus, save_corpus
from app.research.review import ReviewSession, new_session, save_session
from app.schemas.research import IssueInput, SearchPurpose
from app.search.analyzer import analyze_results, select_for_fetch
from app.search.fetcher import fetch_documents
from app.search.opinion import build_queries, collect_corpus_adaptive, find_reaction_candidates, key_terms
from app.search.synthesizer import synthesize_facts


async def run_issue(qwen, search, issue: IssueInput, name: str, out_dir: Path, *, max_questions: int | None = None) -> tuple[ReviewSession, IssueCorpus]:
    """Files are written only after every stage succeeded, so a failed run leaves no half-made session behind."""
    plan = await qwen.expand(issue)
    questions = plan.research_questions[:max_questions]
    relevant, fetched = {}, {}
    for question in questions:
        texts = [q.query for q in plan.queries if q.research_question_id == question.id and q.search_purpose is not SearchPurpose.OPINION_CORPUS]
        if not texts:
            continue
        hits = {}
        for text in texts:  # sequential: gentle on the free API quotas
            for r in await search.search_fact(text):
                hits.setdefault(r.result_id, r)
        analysis = await analyze_results(qwen, issue, plan.decomposition, question, list(hits.values()))
        picked = [a.result for a in select_for_fetch(analysis)]
        for r in picked:
            relevant.setdefault(r.result_id, r)
        for doc in await fetch_documents(picked, question.id):
            if doc.text and (doc.result_id not in fetched or not fetched[doc.result_id].text):
                fetched[doc.result_id] = doc
    fact = await synthesize_facts(qwen, issue, questions, list(fetched.values()))
    used = dict.fromkeys(i for f in [*fact.key_facts, *fact.timeline] for i in f.source_result_ids)
    fact_sources = {i: [relevant[i].title, relevant[i].original_url or relevant[i].url] for i in used if i in relevant}

    queries = build_queries(issue, fact)
    corpus, dropped, search_log = await collect_corpus_adaptive(search, issue, queries, key_terms(issue, plan.decomposition), qwen=qwen, fact=fact)
    found = await find_reaction_candidates(qwen, issue, queries, corpus, dropped, list(plan.protected_terms))
    session = new_session(issue, found, fact, fact_sources)
    issue_corpus = build_corpus(issue, list(relevant.values()), fetched, found.discussion_posts).model_copy(update={"search_log": search_log})

    out_dir.mkdir(parents=True, exist_ok=True)
    save_session(out_dir / f"session_{name}.json", session)
    save_corpus(out_dir / f"corpus_{name}.json", issue_corpus)
    return session, issue_corpus


def main() -> None:
    from dotenv import load_dotenv

    from app.core.config import get_settings
    from app.research.query_expansion import QwenQueryExpansionService
    from app.collectors.community.policy import load_policies
    from app.search.daum import DaumSearchProvider
    from app.search.naver import NaverSearchProvider
    from app.search.service import SearchService

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True)
    p.add_argument("--region", required=True)
    p.add_argument("--issue", required=True)
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--end", type=date.fromisoformat, required=True)
    p.add_argument("--out", type=Path, default=Path("output/research"))
    p.add_argument("--max-questions", type=int, default=None, help="analyze only the first N research questions (faster)")
    a = p.parse_args()
    load_dotenv()
    s = get_settings()
    search = SearchService(naver=NaverSearchProvider(s.naver_client_id or "", s.naver_client_secret or ""), daum=DaumSearchProvider(s.kakao_rest_api_key or ""), community_policies=load_policies())
    issue = IssueInput(region=a.region, start_date=a.start, end_date=a.end, issue=a.issue)
    session, corpus = asyncio.run(run_issue(QwenQueryExpansionService(), search, issue, a.name, a.out, max_questions=a.max_questions))
    dated = sum(1 for i in corpus.items if i.published_at)
    print(f"saved session_{a.name}.json and corpus_{a.name}.json in {a.out}: {len(corpus.items)} items, {dated} with a publish date")


if __name__ == "__main__":
    main()
