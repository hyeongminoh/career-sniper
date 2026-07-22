"""Abstract base class defining the crawl() interface each company crawler implements.

Provides shared utilities so subclasses only need to implement page-specific parsing:
- HTTP fetch for static pages (requests) and JS-rendered pages (Playwright)
- BeautifulSoup parsing helper
- Rate limiting between requests
- Error handling that converts failures into collected error messages instead of crashing
- Logging
"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from graph.state import JobPosting

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # Playwright is optional until `playwright install chromium` has run
    sync_playwright = None
    PlaywrightTimeoutError = TimeoutError

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 CareerSniperBot/1.0"
)


class CrawlerError(Exception):
    """Raised when a crawler fails to fetch or parse a careers page."""


class BaseCrawler(ABC):
    """Shared functionality for all company crawlers.

    Subclasses set `company_name` and implement `crawl()`, using `fetch_static` /
    `fetch_rendered` + `parse_html` to turn a careers page into a list of JobPostings.
    """

    company_name: str = "unknown"

    def __init__(
        self,
        delay_seconds: Optional[float] = None,
        timeout_ms: Optional[int] = None,
        headless: Optional[bool] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self.delay_seconds = (
            delay_seconds if delay_seconds is not None else float(os.getenv("CRAWL_DELAY_SECONDS", "2"))
        )
        self.timeout_ms = (
            timeout_ms if timeout_ms is not None else int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "30000"))
        )
        self.headless = (
            headless if headless is not None else os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
        )
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.logger = logging.getLogger(f"crawler.{self.company_name}")
        self._last_request_at: float = 0.0

    # -- must be implemented per company --
    @abstractmethod
    def crawl(self, keywords: Optional[List[str]] = None) -> List[JobPosting]:
        """Fetch and parse this company's careers page into a list of JobPostings.

        Should raise CrawlerError on failure; let unrelated exceptions propagate.
        """
        raise NotImplementedError

    def safe_crawl(self, keywords: Optional[List[str]] = None) -> Tuple[List[JobPosting], List[str]]:
        """Runs crawl() and converts failures into collected error messages instead of
        raising, so one company's failure doesn't abort the whole graph run.
        """
        try:
            postings = self.crawl(keywords)
            self.logger.info("Collected %d posting(s) from %s", len(postings), self.company_name)
            return postings, []
        except CrawlerError as exc:
            self.logger.error("Crawl failed for %s: %s", self.company_name, exc)
            return [], [f"[{self.company_name}] {exc}"]
        except Exception as exc:  # unexpected errors shouldn't crash the whole pipeline
            self.logger.exception("Unexpected error crawling %s", self.company_name)
            return [], [f"[{self.company_name}] unexpected error: {exc}"]

    # -- rate limiting --
    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait_for = self.delay_seconds - elapsed
        if wait_for > 0:
            self.logger.debug("Rate limiting: sleeping %.2fs", wait_for)
            time.sleep(wait_for)
        self._last_request_at = time.monotonic()

    # -- HTTP fetch for static pages --
    def fetch_static(self, url: str, **request_kwargs) -> str:
        self._respect_rate_limit()
        timeout = request_kwargs.pop("timeout", self.timeout_ms / 1000)
        try:
            response = requests.get(
                url,
                headers={"User-Agent": self.user_agent},
                timeout=timeout,
                **request_kwargs,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self.logger.error("Static fetch failed for %s: %s", url, exc)
            raise CrawlerError(f"Failed to fetch {url}: {exc}") from exc
        return response.text

    # -- HTTP fetch for JSON APIs (GET or POST) --
    def fetch_json(
        self,
        url: str,
        method: str = "GET",
        json_body: Optional[Dict[str, Any]] = None,
        **request_kwargs,
    ) -> Any:
        self._respect_rate_limit()
        timeout = request_kwargs.pop("timeout", self.timeout_ms / 1000)
        try:
            response = requests.request(
                method,
                url,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                json=json_body,
                timeout=timeout,
                **request_kwargs,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self.logger.error("%s request failed for %s: %s", method, url, exc)
            raise CrawlerError(f"Failed to {method} {url}: {exc}") from exc
        try:
            return response.json()
        except ValueError as exc:
            raise CrawlerError(f"Response from {url} was not valid JSON: {exc}") from exc

    # -- Playwright fetch for JS-rendered pages --
    def fetch_rendered(self, url: str, wait_selector: Optional[str] = None) -> str:
        if sync_playwright is None:
            raise CrawlerError(
                "Playwright is not installed. Run `pip install playwright && playwright install chromium`."
            )
        self._respect_rate_limit()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self.headless)
                try:
                    page = browser.new_page(user_agent=self.user_agent)
                    page.goto(url, timeout=self.timeout_ms)
                    if wait_selector:
                        page.wait_for_selector(wait_selector, timeout=self.timeout_ms)
                    html = page.content()
                finally:
                    browser.close()
        except PlaywrightTimeoutError as exc:
            self.logger.error("Rendered fetch timed out for %s: %s", url, exc)
            raise CrawlerError(f"Timed out waiting for {url}: {exc}") from exc
        except Exception as exc:
            self.logger.error("Rendered fetch failed for %s: %s", url, exc)
            raise CrawlerError(f"Failed to render {url}: {exc}") from exc
        return html

    # -- parsing helper --
    @staticmethod
    def parse_html(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    # -- shared JobPosting builder --
    def make_posting(self, title: str, jd_text: str, url: str) -> JobPosting:
        return JobPosting(
            company=self.company_name,
            title=title.strip(),
            jd_text=jd_text.strip(),
            url=url,
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )
