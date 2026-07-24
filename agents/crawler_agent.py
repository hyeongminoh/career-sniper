"""LangGraph node: dispatches company crawlers and writes raw JD postings into SQLite."""

from __future__ import annotations

import logging
from typing import Dict, List, Type

from config.settings import JOB_SEARCH_KEYWORDS
from crawlers.anthropic_crawler import AnthropicCrawler
from crawlers.base_crawler import BaseCrawler
from crawlers.google_crawler import GoogleCrawler
from crawlers.openai_crawler import OpenAICrawler
from crawlers.palantir_crawler import PalantirCrawler
from crawlers.salesforce_crawler import SalesforceCrawler
from db.database import get_session
from db.repository import save_job_postings
from graph.state import AgentState, JobPosting

logger = logging.getLogger(__name__)

CRAWLERS_BY_COMPANY: Dict[str, Type[BaseCrawler]] = {
    "anthropic": AnthropicCrawler,
    "google": GoogleCrawler,
    "salesforce": SalesforceCrawler,
    "palantir": PalantirCrawler,
    "openai": OpenAICrawler,
}


def crawler_agent(state: AgentState) -> dict:
    """Crawls every company in state['target_companies'], persists postings to SQLite,
    and returns the postings/errors for the rest of the graph to consume.
    """
    target_companies = state.get("target_companies") or list(CRAWLERS_BY_COMPANY.keys())
    keywords = state.get("target_keywords") or JOB_SEARCH_KEYWORDS

    all_postings: List[JobPosting] = []
    all_errors: List[str] = []

    for company in target_companies:
        crawler_cls = CRAWLERS_BY_COMPANY.get(company.strip().lower())
        if crawler_cls is None:
            all_errors.append(f"[{company}] no crawler registered for this company")
            continue

        crawler = crawler_cls()
        postings, errors = crawler.safe_crawl(keywords=keywords)
        all_postings.extend(postings)
        all_errors.extend(errors)

    if all_postings:
        with get_session() as session:
            save_job_postings(session, all_postings)
        logger.info("Persisted %d job posting(s) to the database", len(all_postings))

    return {"job_postings": all_postings, "errors": all_errors}
