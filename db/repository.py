"""Read/write helpers bridging graph.state TypedDicts and db.models ORM records.

Agents call these instead of touching SQLAlchemy sessions/models directly, e.g.:

    with get_session() as session:
        save_job_postings(session, state["job_postings"])
"""

from __future__ import annotations

from typing import List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from db.models import (
    AppealStrategyRecord,
    JDAnalysisRecord,
    JobPostingRecord,
    ResumeGapAnalysisRecord,
    ResumeSnapshotRecord,
)
from graph.state import AppealStrategy, JDAnalysis, JobPosting, ResumeGapAnalysis

ModelT = TypeVar("ModelT")


def _upsert(session: Session, model: Type[ModelT], pk_value: str, data: dict) -> ModelT:
    """Updates the row for `pk_value` if it exists, else inserts a new one."""
    existing = session.get(model, pk_value)
    if existing is not None:
        for key, value in data.items():
            setattr(existing, key, value)
        return existing
    record = model(**data)
    session.add(record)
    return record


# -- writes --------------------------------------------------------------


def save_job_postings(session: Session, postings: List[JobPosting]) -> None:
    """Upserts by url: a posting seen again on a later crawl refreshes its jd_text /
    scraped_at instead of creating a duplicate row."""
    for posting in postings:
        _upsert(session, JobPostingRecord, posting["url"], dict(posting))


def save_jd_analyses(session: Session, analyses: List[JDAnalysis]) -> None:
    for analysis in analyses:
        _upsert(session, JDAnalysisRecord, analysis["posting_url"], dict(analysis))


def save_gap_analyses(session: Session, gaps: List[ResumeGapAnalysis]) -> None:
    for gap in gaps:
        _upsert(session, ResumeGapAnalysisRecord, gap["posting_url"], dict(gap))


def save_appeal_strategies(session: Session, strategies: List[AppealStrategy]) -> None:
    for strategy in strategies:
        _upsert(session, AppealStrategyRecord, strategy["posting_url"], dict(strategy))


def save_resume_snapshot(session: Session, file_path: str, resume_text: str) -> ResumeSnapshotRecord:
    snapshot = ResumeSnapshotRecord(file_path=file_path, resume_text=resume_text)
    session.add(snapshot)
    session.flush()
    return snapshot


# -- reads -----------------------------------------------------------------


def get_all_postings_with_analysis(session: Session) -> List[JobPostingRecord]:
    """Every posting with its jd_analysis / gap_analysis / appeal_strategy eager-loaded,
    newest first — the shape the Streamlit UI browses. Eager-loading matters here because
    get_session() closes the session on exit, and lazily-loaded relationships raise once
    the session that would fetch them is gone."""
    stmt = (
        select(JobPostingRecord)
        .options(
            selectinload(JobPostingRecord.jd_analysis),
            selectinload(JobPostingRecord.gap_analysis),
            selectinload(JobPostingRecord.appeal_strategy),
        )
        .order_by(JobPostingRecord.scraped_at.desc())
    )
    return list(session.scalars(stmt))


def get_latest_resume_snapshot(session: Session) -> Optional[ResumeSnapshotRecord]:
    stmt = select(ResumeSnapshotRecord).order_by(ResumeSnapshotRecord.created_at.desc()).limit(1)
    return session.scalars(stmt).first()
