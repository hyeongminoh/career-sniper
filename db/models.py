"""SQLite table schemas: job_postings, jd_analyses, resume_gap_analyses, appeal_strategies,
resume_snapshots.

Mirrors the shapes in graph.state (JobPosting, JDAnalysis, ResumeGapAnalysis, AppealStrategy)
so crawler/analyzer/matcher/recommender agents can persist their LangGraph state as-is.
`url` / `posting_url` is the join key threaded through every table, matching graph.state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class JobPostingRecord(Base):
    """One JD collected by a crawler. `url` is the natural unique key across the pipeline."""

    __tablename__ = "job_postings"

    url: Mapped[str] = mapped_column(String, primary_key=True)
    company: Mapped[str] = mapped_column(String, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    jd_text: Mapped[str] = mapped_column(Text, nullable=False)
    scraped_at: Mapped[str] = mapped_column(String, nullable=False)  # ISO 8601, set by crawlers

    jd_analysis: Mapped[Optional[JDAnalysisRecord]] = relationship(
        back_populates="posting", uselist=False, cascade="all, delete-orphan"
    )
    gap_analysis: Mapped[Optional[ResumeGapAnalysisRecord]] = relationship(
        back_populates="posting", uselist=False, cascade="all, delete-orphan"
    )
    appeal_strategy: Mapped[Optional[AppealStrategyRecord]] = relationship(
        back_populates="posting", uselist=False, cascade="all, delete-orphan"
    )


class JDAnalysisRecord(Base):
    """Structured extraction of one JobPostingRecord, produced by JD Analyzer Agent.

    One row per posting_url — rerunning analysis on the same posting overwrites the
    previous result rather than accumulating history.
    """

    __tablename__ = "jd_analyses"

    posting_url: Mapped[str] = mapped_column(ForeignKey("job_postings.url"), primary_key=True)
    company: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    core_competencies: Mapped[List[str]] = mapped_column(JSON, default=list)
    tech_stack: Mapped[List[str]] = mapped_column(JSON, default=list)
    experience_requirements: Mapped[str] = mapped_column(Text, default="")
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    posting: Mapped[JobPostingRecord] = relationship(back_populates="jd_analysis")


class ResumeGapAnalysisRecord(Base):
    """Comparison of the resume against one JDAnalysisRecord, produced by Resume Matcher Agent."""

    __tablename__ = "resume_gap_analyses"

    posting_url: Mapped[str] = mapped_column(ForeignKey("job_postings.url"), primary_key=True)
    company: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    matched_points: Mapped[List[str]] = mapped_column(JSON, default=list)
    missing_points: Mapped[List[str]] = mapped_column(JSON, default=list)
    match_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0-1.0
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    posting: Mapped[JobPostingRecord] = relationship(back_populates="gap_analysis")


class AppealStrategyRecord(Base):
    """Concrete resume edit recommendations for one posting, produced by Recommender Agent."""

    __tablename__ = "appeal_strategies"

    posting_url: Mapped[str] = mapped_column(ForeignKey("job_postings.url"), primary_key=True)
    company: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    resume_edit_suggestions: Mapped[List[str]] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String, default="medium")  # "high" | "medium" | "low"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    posting: Mapped[JobPostingRecord] = relationship(back_populates="appeal_strategy")


class ResumeSnapshotRecord(Base):
    """A saved copy of the parsed resume text at a point in time, so which resume version
    a given gap analysis / appeal strategy was run against stays traceable even after the
    resume file on disk changes."""

    __tablename__ = "resume_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
