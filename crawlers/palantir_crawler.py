"""Crawler for Palantir careers page.

Palantir's job board runs on Lever (jobs.lever.co/palantir). Lever exposes a public,
unauthenticated JSON API for postings, so this crawler calls that directly instead of
scraping the rendered job board.

API reference: https://github.com/lever/postings-api
"""

from __future__ import annotations

from typing import List, Optional

from crawlers.base_crawler import BaseCrawler, CrawlerError
from graph.state import JobPosting

LEVER_SITE = "palantir"
POSTINGS_API_URL = f"https://api.lever.co/v0/postings/{LEVER_SITE}?mode=json"


class PalantirCrawler(BaseCrawler):
    """Crawls Palantir job postings via Lever's public postings API."""

    company_name = "Palantir"

    def crawl(self, keywords: Optional[List[str]] = None) -> List[JobPosting]:
        postings_raw = self.fetch_json(POSTINGS_API_URL)
        if not isinstance(postings_raw, list):
            raise CrawlerError(f"Unexpected Lever response shape for site '{LEVER_SITE}': expected a list")
        if not postings_raw:
            raise CrawlerError(f"Lever API returned no postings for site '{LEVER_SITE}'")

        normalized_keywords = [kw.lower() for kw in keywords] if keywords else None

        postings: List[JobPosting] = []
        for job in postings_raw:
            title = (job.get("text") or "").strip()
            if normalized_keywords and not any(kw in title.lower() for kw in normalized_keywords):
                continue

            jd_text = self._extract_text(job)
            url = job.get("hostedUrl") or job.get("applyUrl") or ""
            if not title or not jd_text or not url:
                self.logger.warning("Skipping incomplete job entry: id=%s", job.get("id"))
                continue

            postings.append(self.make_posting(title=title, jd_text=jd_text, url=url))

        return postings

    def _extract_text(self, job: dict) -> str:
        """Lever splits a posting into a main `description` plus several labeled
        `lists` (e.g. "What you'll do", "Requirements"); stitch them into one JD text."""
        sections: List[str] = []

        description_plain = (job.get("descriptionPlain") or "").strip()
        if description_plain:
            sections.append(description_plain)
        elif job.get("description"):
            sections.append(self.parse_html(job["description"]).get_text(separator="\n", strip=True))

        for section in job.get("lists") or []:
            heading = (section.get("text") or "").strip()
            content_text = self.parse_html(section.get("content") or "").get_text(separator="\n", strip=True)
            if heading or content_text:
                sections.append(f"{heading}\n{content_text}".strip())

        return "\n\n".join(s for s in sections if s)
