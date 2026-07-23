"""LangGraph node: uses the Anthropic API to extract structured requirements (skills, seniority, keywords) from raw JD text."""

from __future__ import annotations

import json
import logging
from typing import List

import anthropic

from config.settings import ANTHROPIC_MODEL, require_anthropic_api_key
from db.database import get_session
from db.repository import save_jd_analyses
from graph.state import AgentState, JDAnalysis, JobPosting

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a technical recruiter analyzing a job description. Extract the information "
    "requested, staying strictly grounded in the text provided — do not invent requirements "
    "the posting doesn't state."
)

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "core_competencies": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Key non-technical or role-level competencies the posting emphasizes "
                "(e.g. 'cross-functional leadership', 'stakeholder communication')."
            ),
        },
        "tech_stack": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific technologies, languages, frameworks, or tools named in the posting.",
        },
        "experience_requirements": {
            "type": "string",
            "description": (
                "A one- to two-sentence summary of the required years of experience, "
                "seniority level, and educational requirements."
            ),
        },
    },
    "required": ["core_competencies", "tech_stack", "experience_requirements"],
    "additionalProperties": False,
}


def _analyze_posting(client: anthropic.Anthropic, posting: JobPosting) -> JDAnalysis:
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": ANALYSIS_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": f"Job title: {posting['title']}\n\nJob description:\n{posting['jd_text']}",
            }
        ],
    )
    text = next(block.text for block in response.content if block.type == "text")
    parsed = json.loads(text)

    return JDAnalysis(
        posting_url=posting["url"],
        company=posting["company"],
        title=posting["title"],
        core_competencies=parsed["core_competencies"],
        tech_stack=parsed["tech_stack"],
        experience_requirements=parsed["experience_requirements"],
    )


def jd_analyzer_agent(state: AgentState) -> dict:
    """Analyzes every job_posting in state and returns the resulting JDAnalysis list."""
    require_anthropic_api_key()
    client = anthropic.Anthropic()

    analyses: List[JDAnalysis] = []
    errors: List[str] = []

    for posting in state.get("job_postings", []):
        try:
            analyses.append(_analyze_posting(client, posting))
        except Exception as exc:
            logger.exception("JD analysis failed for %s", posting.get("url"))
            errors.append(f"[jd_analyzer] {posting.get('company')} — {posting.get('title')}: {exc}")

    if analyses:
        with get_session() as session:
            save_jd_analyses(session, analyses)
        logger.info("Persisted %d JD analysis record(s)", len(analyses))

    return {"jd_analyses": analyses, "errors": errors}
