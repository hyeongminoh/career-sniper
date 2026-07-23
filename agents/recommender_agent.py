"""LangGraph node: turns the resume/JD gap analysis into concrete resume edit recommendations."""

from __future__ import annotations

import json
import logging
from typing import List

import anthropic

from config.settings import ANTHROPIC_MODEL, require_anthropic_api_key
from db.database import get_session
from db.repository import save_appeal_strategies
from graph.state import AgentState, AppealStrategy, ResumeGapAnalysis

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a resume coach. Given a gap analysis between a candidate's resume and a job "
    "posting, write concrete, actionable edits the candidate can make to their resume. "
    "Prefer specific line-level suggestions (what to add, reword, or reorder) over generic "
    "advice like 'highlight your experience'. Ground suggestions in the resume's actual "
    "content and the JD's actual missing points — do not invent experience the candidate "
    "doesn't have; instead suggest how to phrase what they do have to better match the JD."
)

STRATEGY_SCHEMA = {
    "type": "object",
    "properties": {
        "resume_edit_suggestions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete, specific edits to make to the resume for this posting.",
        },
        "priority": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": (
                "How urgent it is to tailor the resume for this specific posting, based on "
                "match_score and how many high-value points are missing."
            ),
        },
    },
    "required": ["resume_edit_suggestions", "priority"],
    "additionalProperties": False,
}


def _build_strategy(
    client: anthropic.Anthropic, resume_text: str, gap: ResumeGapAnalysis
) -> AppealStrategy:
    gap_summary = (
        f"Match score: {gap['match_score']:.2f}\n"
        f"Already matched: {', '.join(gap['matched_points']) or 'none'}\n"
        f"Missing: {', '.join(gap['missing_points']) or 'none'}"
    )
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": STRATEGY_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Job: {gap['company']} — {gap['title']}\n\nGap analysis:\n{gap_summary}\n\n"
                    f"Candidate resume:\n{resume_text}"
                ),
            }
        ],
    )
    text = next(block.text for block in response.content if block.type == "text")
    parsed = json.loads(text)

    return AppealStrategy(
        posting_url=gap["posting_url"],
        company=gap["company"],
        title=gap["title"],
        resume_edit_suggestions=parsed["resume_edit_suggestions"],
        priority=parsed["priority"],
    )


def recommender_agent(state: AgentState) -> dict:
    """Turns every gap_analysis in state into an AppealStrategy."""
    resume_text = state.get("resume_text", "")
    require_anthropic_api_key()
    client = anthropic.Anthropic()

    strategies: List[AppealStrategy] = []
    errors: List[str] = []

    for gap in state.get("gap_analyses", []):
        try:
            strategies.append(_build_strategy(client, resume_text, gap))
        except Exception as exc:
            logger.exception("Recommendation failed for %s", gap.get("posting_url"))
            errors.append(f"[recommender] {gap.get('company')} — {gap.get('title')}: {exc}")

    if strategies:
        with get_session() as session:
            save_appeal_strategies(session, strategies)
        logger.info("Persisted %d appeal strategy record(s)", len(strategies))

    return {"appeal_strategies": strategies, "errors": errors}
