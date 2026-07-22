"""Crawler for OpenAI careers page.

OpenAI's job board runs on Ashby (jobs.ashbyhq.com/openai). Ashby exposes a public,
unauthenticated Job Posting API that returns every open role for an organization in a
single response, so this crawler calls that directly instead of scraping the rendered SPA.

API reference: https://developers.ashbyhq.com/docs/public-job-posting-api
"""

from __future__ import annotations

from typing import List, Optional

from crawlers.base_crawler import BaseCrawler, CrawlerError
from graph.state import JobPosting

ASHBY_JOB_BOARD_NAME = "openai"
JOB_BOARD_API_URL = f"https://api.ashbyhq.com/posting-api/job-board/{ASHBY_JOB_BOARD_NAME}"


class OpenAICrawler(BaseCrawler):
    """Crawls OpenAI job postings via Ashby's public Job Posting API."""

    company_name = "OpenAI"

    def crawl(self, keywords: Optional[List[str]] = None) -> List[JobPosting]:
        payload = self.fetch_json(JOB_BOARD_API_URL)
        jobs = payload.get("jobs")
        if jobs is None:
            raise CrawlerError(f"Unexpected Ashby response shape for board '{ASHBY_JOB_BOARD_NAME}': no 'jobs' key")
        if not jobs:
            raise CrawlerError(f"Ashby API returned no jobs for board '{ASHBY_JOB_BOARD_NAME}'")

        normalized_keywords = [kw.lower() for kw in keywords] if keywords else None

        postings: List[JobPosting] = []
        for job in jobs:
            title = (job.get("title") or "").strip()
            if normalized_keywords and not any(kw in title.lower() for kw in normalized_keywords):
                continue

            jd_text = self._extract_text(job.get("descriptionHtml") or "")
            url = job.get("jobUrl") or job.get("applyUrl") or ""
            if not title or not jd_text or not url:
                self.logger.warning("Skipping incomplete job entry: id=%s", job.get("id"))
                continue

            postings.append(self.make_posting(title=title, jd_text=jd_text, url=url))

        return postings

    def _extract_text(self, html_content: str) -> str:
        if not html_content:
            return ""
        return self.parse_html(html_content).get_text(separator="\n", strip=True)
