"""Loads environment variables (.env) and exposes app-wide config constants."""

from __future__ import annotations

import os
from typing import List

from dotenv import load_dotenv

load_dotenv()

# -- Anthropic API --
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")

# -- Companies crawled by default (keys into agents.crawler_agent.CRAWLERS_BY_COMPANY) --
DEFAULT_TARGET_COMPANIES: List[str] = ["Anthropic", "Google", "Salesforce", "Palantir", "OpenAI"]


def parse_csv(raw: str) -> List[str]:
    """Splits a comma-separated string into a trimmed, non-empty list of items.
    Shared with ui/app.py so the keyword text input parses the same way as this default."""
    return [item.strip() for item in raw.split(",") if item.strip()]


# Default job search keywords, used by the CLI (main.py) and as the Streamlit UI's
# pre-filled value — the UI lets the keywords be edited per run instead of only via .env.
JOB_SEARCH_KEYWORDS: List[str] = parse_csv(
    os.getenv("JOB_SEARCH_KEYWORDS", "Software Engineer,Machine Learning Engineer,Product Manager")
)

# -- Resume --
RESUME_FILE_PATH: str = os.getenv("RESUME_FILE_PATH", "resume/my_resume.pdf")

# -- Database (mirrors db.database's own default; kept independent to avoid coupling
# the DB connection module to this settings module) --
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/career_sniper.db")

# -- Streamlit --
STREAMLIT_SERVER_PORT: int = int(os.getenv("STREAMLIT_SERVER_PORT", "8501"))


def require_anthropic_api_key() -> str:
    """Raises a clear error at call time (not import time) if the API key is missing,
    so importing config.settings doesn't itself require a working .env."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in.")
    return ANTHROPIC_API_KEY
