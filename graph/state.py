"""Shared LangGraph state schema (TypedDict) passed between crawler / analyzer / matcher / recommender nodes.

Each downstream record carries `posting_url` as a join key back to the JobPosting it
originated from, since JD analysis / gap analysis / appeal strategy are produced one-per-posting.
"""

from __future__ import annotations

import operator
from typing import Annotated, List, TypedDict


class JobPosting(TypedDict):
    """One JD collected by a crawler."""

    company: str
    title: str
    jd_text: str
    url: str
    scraped_at: str  # ISO 8601 timestamp


class JDAnalysis(TypedDict):
    """Structured extraction of a single JobPosting, produced by JD Analyzer Agent."""

    posting_url: str
    company: str
    title: str
    core_competencies: List[str]
    tech_stack: List[str]
    experience_requirements: str


class ResumeGapAnalysis(TypedDict):
    """Comparison of the resume against one JDAnalysis, produced by Resume Matcher Agent."""

    posting_url: str
    company: str
    title: str
    matched_points: List[str]
    missing_points: List[str]
    match_score: float  # 0.0 (no overlap) - 1.0 (full match)


class AppealStrategy(TypedDict):
    """Concrete resume edit recommendations for one posting, produced by Recommender Agent."""

    posting_url: str
    company: str
    title: str
    resume_edit_suggestions: List[str]
    priority: str  # "high" | "medium" | "low"


class AgentState(TypedDict):
    """State threaded through the crawler -> jd_analyzer -> resume_matcher -> recommender graph.

    List fields use `operator.add` as a reducer so nodes that fan out per-company or
    per-posting (parallel branches) can each return a partial list and have them merged,
    instead of overwriting each other.
    """

    # -- input / config, set once up front --
    target_companies: List[str]
    resume_text: str

    # -- accumulated across (possibly parallel) node runs --
    job_postings: Annotated[List[JobPosting], operator.add]
    jd_analyses: Annotated[List[JDAnalysis], operator.add]
    gap_analyses: Annotated[List[ResumeGapAnalysis], operator.add]
    appeal_strategies: Annotated[List[AppealStrategy], operator.add]
    errors: Annotated[List[str], operator.add]
