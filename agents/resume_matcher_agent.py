"""LangGraph node: compares parsed resume content against analyzed JD requirements and scores the gap."""

from __future__ import annotations

import json
import logging
from typing import List

import anthropic

from config.settings import ANTHROPIC_MODEL, require_anthropic_api_key
from db.database import get_session
from db.repository import save_gap_analyses
from graph.state import AgentState, JDAnalysis, ResumeGapAnalysis

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a career coach comparing a candidate's resume against a job description's "
    "requirements. Identify what the resume already demonstrates and what it's missing. "
    "Be specific and grounded in both texts — do not invent resume content that isn't there."
)

GAP_SCHEMA = {
    "type": "object",
    "properties": {
        "matched_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Specific JD requirements the resume already demonstrates, referencing "
                "what the resume actually says."
            ),
        },
        "missing_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific JD requirements the resume does not clearly demonstrate.",
        },
        "match_score": {
            "type": "number",
            "description": "Overall fit from 0.0 (no overlap) to 1.0 (fully matches the JD).",
        },
    },
    "required": ["matched_points", "missing_points", "match_score"],
    "additionalProperties": False,
}


def _score_gap(client: anthropic.Anthropic, resume_text: str, analysis: JDAnalysis) -> ResumeGapAnalysis:
    jd_summary = (
        f"Core competencies: {', '.join(analysis['core_competencies']) or 'none listed'}\n"
        f"Tech stack: {', '.join(analysis['tech_stack']) or 'none listed'}\n"
        f"Experience requirements: {analysis['experience_requirements']}"
    )
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": GAP_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Job requirements ({analysis['company']} — {analysis['title']}):\n{jd_summary}\n\n"
                    f"Candidate resume:\n{resume_text}"
                ),
            }
        ],
    )
    text = next(block.text for block in response.content if block.type == "text")
    parsed = json.loads(text)

    return ResumeGapAnalysis(
        posting_url=analysis["posting_url"],
        company=analysis["company"],
        title=analysis["title"],
        matched_points=parsed["matched_points"],
        missing_points=parsed["missing_points"],
        match_score=float(parsed["match_score"]),
    )


def resume_matcher_agent(state: AgentState) -> dict:
    """Scores every jd_analysis in state against state['resume_text']."""
    resume_text = state.get("resume_text", "")
    if not resume_text.strip():
        return {"errors": ["[resume_matcher] resume_text is empty — nothing to compare against"]}

    require_anthropic_api_key()
    client = anthropic.Anthropic()

    gap_analyses: List[ResumeGapAnalysis] = []
    errors: List[str] = []

    for analysis in state.get("jd_analyses", []):
        try:
            gap_analyses.append(_score_gap(client, resume_text, analysis))
        except Exception as exc:
            logger.exception("Gap analysis failed for %s", analysis.get("posting_url"))
            errors.append(f"[resume_matcher] {analysis.get('company')} — {analysis.get('title')}: {exc}")

    if gap_analyses:
        with get_session() as session:
            save_gap_analyses(session, gap_analyses)
        logger.info("Persisted %d gap analysis record(s)", len(gap_analyses))

    return {"gap_analyses": gap_analyses, "errors": errors}
