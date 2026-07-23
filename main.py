"""CLI entry point: runs the compiled LangGraph workflow end-to-end (crawl -> analyze -> match -> recommend)."""

from __future__ import annotations

import logging
import sys

from config.settings import DEFAULT_TARGET_COMPANIES, RESUME_FILE_PATH
from db.database import get_session, init_db
from db.repository import save_resume_snapshot
from graph.workflow import build_workflow
from resume_loader import ResumeLoadError, load_resume_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    init_db()

    try:
        resume_text = load_resume_text(RESUME_FILE_PATH)
    except ResumeLoadError as exc:
        logger.error(str(exc))
        return 1

    with get_session() as session:
        save_resume_snapshot(session, RESUME_FILE_PATH, resume_text)

    workflow = build_workflow()
    initial_state = {
        "target_companies": DEFAULT_TARGET_COMPANIES,
        "resume_text": resume_text,
        "job_postings": [],
        "jd_analyses": [],
        "gap_analyses": [],
        "appeal_strategies": [],
        "errors": [],
    }

    final_state = workflow.invoke(initial_state)

    logger.info(
        "Done: %d posting(s), %d JD analysis, %d gap analysis, %d recommendation(s), %d error(s)",
        len(final_state.get("job_postings", [])),
        len(final_state.get("jd_analyses", [])),
        len(final_state.get("gap_analyses", [])),
        len(final_state.get("appeal_strategies", [])),
        len(final_state.get("errors", [])),
    )
    for error in final_state.get("errors", []):
        logger.warning(error)

    return 0


if __name__ == "__main__":
    sys.exit(main())
