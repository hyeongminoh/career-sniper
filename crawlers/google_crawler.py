"""Crawler for Google careers page.

Google's careers site (google.com/about/careers/applications/jobs/results) is a
client-side-rendered SPA with no public JSON API (Google retired its old Jobs API in
2021). This crawler uses BaseCrawler.fetch_rendered() (Playwright) to load the search
results and each job detail page, then extracts text with BeautifulSoup.

CAUTION: unlike the Greenhouse/Lever/Ashby-backed crawlers, there is no stable public
contract here. Google's auto-generated CSS class names change across deploys, so this
crawler deliberately avoids hardcoded class selectors and relies on the one structural
fact confirmed stable: job detail links match `/jobs/results/<numeric-id>-<slug>/`. It
only reads the first rendered batch of results — Google paginates behind a "Show more
results" button that this crawler does not click. Verify against the live site and
extend pagination handling before relying on this for full coverage.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple
from urllib.parse import urlencode, urljoin

from crawlers.base_crawler import BaseCrawler, CrawlerError
from graph.state import JobPosting

SEARCH_RESULTS_URL = "https://www.google.com/about/careers/applications/jobs/results"
BASE_URL = "https://www.google.com"
RESULTS_LINK_SELECTOR = "a[href*='/jobs/results/']"
JOB_LINK_PATTERN = re.compile(r"/jobs/results/\d+-")


class GoogleCrawler(BaseCrawler):
    """Crawls Google job postings by rendering the careers SPA with Playwright."""

    company_name = "Google"

    def crawl(self, keywords: Optional[List[str]] = None) -> List[JobPosting]:
        search_url = SEARCH_RESULTS_URL
        if keywords:
            search_url = f"{SEARCH_RESULTS_URL}?{urlencode({'q': ' '.join(keywords)})}"

        job_links = self._collect_job_links(search_url)
        if not job_links:
            raise CrawlerError("No job links found on Google careers search results page")

        postings: List[JobPosting] = []
        for title, url in job_links:
            jd_text = self._fetch_job_description(url)
            if not jd_text:
                self.logger.warning("Skipping job with no extractable description: %s", url)
                continue
            postings.append(self.make_posting(title=title, jd_text=jd_text, url=url))

        return postings

    def _collect_job_links(self, search_url: str) -> List[Tuple[str, str]]:
        html = self.fetch_rendered(search_url, wait_selector=RESULTS_LINK_SELECTOR)
        soup = self.parse_html(html)

        seen_urls = set()
        links: List[Tuple[str, str]] = []
        for anchor in soup.select(RESULTS_LINK_SELECTOR):
            href = anchor.get("href") or ""
            if not JOB_LINK_PATTERN.search(href):
                continue

            url = urljoin(BASE_URL, href)
            if url in seen_urls:
                continue

            title = anchor.get_text(strip=True)
            if not title:
                heading = anchor.find(["h1", "h2", "h3"])
                title = heading.get_text(strip=True) if heading else ""
            if not title:
                continue

            seen_urls.add(url)
            links.append((title, url))

        return links

    def _fetch_job_description(self, url: str) -> str:
        try:
            html = self.fetch_rendered(url)
        except CrawlerError as exc:
            self.logger.warning("Failed to render job detail page %s: %s", url, exc)
            return ""

        soup = self.parse_html(html)
        for noise in soup(["script", "style", "nav", "header", "footer"]):
            noise.decompose()

        main = soup.find("main") or soup.body
        return main.get_text(separator="\n", strip=True) if main else ""
