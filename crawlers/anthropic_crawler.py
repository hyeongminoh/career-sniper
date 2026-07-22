"""Crawler for Anthropic careers page.

Anthropic's job board is hosted on Greenhouse (job-boards.greenhouse.io/anthropic).
Rather than scraping the rendered HTML table, this crawler calls Greenhouse's public
JSON API, which returns every posting's full description as HTML in one request.
No Playwright/JS rendering is needed here.

API reference: https://boards-api.greenhouse.io/v1/boards/anthropic/jobs?content=true
"""

from __future__ import annotations

import json
from typing import List, Optional

from crawlers.base_crawler import BaseCrawler, CrawlerError
from graph.state import JobPosting

GREENHOUSE_BOARD_TOKEN = "anthropic"
JOBS_API_URL = f"https://boards-api.greenhouse.io/v1/boards/{GREENHOUSE_BOARD_TOKEN}/jobs?content=true"


class AnthropicCrawler(BaseCrawler):
    """Crawls Anthropic job postings via Greenhouse's public JSON API."""

    company_name = "Anthropic"

    def crawl(self, keywords: Optional[List[str]] = None) -> List[JobPosting]:
        raw = self.fetch_static(JOBS_API_URL)

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CrawlerError(f"Could not parse Greenhouse response as JSON: {exc}") from exc

        jobs = payload.get("jobs", [])
        if not jobs:
            raise CrawlerError("Greenhouse API returned no jobs for board 'anthropic'")

        normalized_keywords = [kw.lower() for kw in keywords] if keywords else None

        postings: List[JobPosting] = []
        for job in jobs:
            title = (job.get("title") or "").strip()
            if normalized_keywords and not any(kw in title.lower() for kw in normalized_keywords):
                continue

            jd_text = self._extract_text(job.get("content") or "")
            url = job.get("absolute_url") or ""
            if not title or not jd_text or not url:
                self.logger.warning("Skipping incomplete job entry: id=%s", job.get("id"))
                continue

            postings.append(self.make_posting(title=title, jd_text=jd_text, url=url))

        return postings

    def _extract_text(self, html_content: str) -> str:
        """Greenhouse's `content` field is raw HTML; strip tags down to readable JD text."""
        if not html_content:
            return ""
        soup = self.parse_html(html_content)
        return soup.get_text(separator="\n", strip=True)
