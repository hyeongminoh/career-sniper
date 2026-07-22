"""Crawler for Salesforce careers page.

Salesforce's job board runs on Workday (salesforce.wd12.myworkdayjobs.com/External_Career_Site).
Workday's frontend calls an internal JSON API under `/wday/cxs/{tenant}/{site}/...` to
list and fetch postings; this crawler calls that directly instead of driving a browser
against the rendered SPA.

NOTE: unlike the Greenhouse/Lever/Ashby endpoints used by the other crawlers, this Workday
CXS API is not officially documented and its exact response shape can vary by Workday
version/tenant. The field names below (`jobPostings`, `externalPath`,
`jobPostingInfo.jobDescription`, ...) match the pattern seen across most Workday-hosted
career sites, but this crawler has not been live-verified end to end (the endpoint's
existence was confirmed, but it requires POST and the response body wasn't inspected).
Smoke-test against the live tenant and adjust field names here if it breaks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from crawlers.base_crawler import BaseCrawler, CrawlerError
from graph.state import JobPosting

WORKDAY_TENANT = "salesforce"
WORKDAY_HOST = "salesforce.wd12.myworkdayjobs.com"
WORKDAY_SITE = "External_Career_Site"

CXS_BASE_URL = f"https://{WORKDAY_HOST}/wday/cxs/{WORKDAY_TENANT}/{WORKDAY_SITE}"
JOBS_LIST_URL = f"{CXS_BASE_URL}/jobs"
PAGE_SIZE = 20
MAX_PAGES = 25  # safety cap: up to 500 postings, so a bad `total` value can't loop forever


class SalesforceCrawler(BaseCrawler):
    """Crawls Salesforce job postings via Workday's internal CXS JSON API."""

    company_name = "Salesforce"

    def crawl(self, keywords: Optional[List[str]] = None) -> List[JobPosting]:
        listings = self._fetch_all_listings()
        if not listings:
            raise CrawlerError(f"Workday API returned no jobs for tenant '{WORKDAY_TENANT}'")

        normalized_keywords = [kw.lower() for kw in keywords] if keywords else None

        postings: List[JobPosting] = []
        for job in listings:
            title = (job.get("title") or "").strip()
            external_path = job.get("externalPath") or ""
            if normalized_keywords and not any(kw in title.lower() for kw in normalized_keywords):
                continue
            if not title or not external_path:
                self.logger.warning("Skipping incomplete listing entry: %s", job)
                continue

            jd_text, url = self._fetch_detail(external_path)
            if not jd_text or not url:
                self.logger.warning("Skipping job with no fetchable detail: %s", title)
                continue

            postings.append(self.make_posting(title=title, jd_text=jd_text, url=url))

        return postings

    def _fetch_all_listings(self) -> List[Dict[str, Any]]:
        """Pages through the Workday jobs-list endpoint (limit/offset) until it runs
        out of results or hits `total`."""
        listings: List[Dict[str, Any]] = []
        offset = 0
        total: Optional[int] = None

        for _ in range(MAX_PAGES):
            body = {"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": ""}
            payload = self.fetch_json(JOBS_LIST_URL, method="POST", json_body=body)

            if total is None:
                total = payload.get("total", 0)

            page_jobs = payload.get("jobPostings") or []
            if not page_jobs:
                break
            listings.extend(page_jobs)

            offset += PAGE_SIZE
            if total is not None and offset >= total:
                break

        return listings

    def _fetch_detail(self, external_path: str) -> Tuple[str, str]:
        detail_url = f"{CXS_BASE_URL}{external_path}"
        try:
            payload = self.fetch_json(detail_url, method="POST", json_body={})
        except CrawlerError as exc:
            self.logger.warning("Failed to fetch job detail at %s: %s", detail_url, exc)
            return "", ""

        info = payload.get("jobPostingInfo") or {}
        description_html = info.get("jobDescription") or ""
        jd_text = self.parse_html(description_html).get_text(separator="\n", strip=True) if description_html else ""
        url = info.get("externalUrl") or f"https://{WORKDAY_HOST}/en-US/{WORKDAY_SITE}{external_path}"
        return jd_text, url
