"""Streamlit UI: trigger crawl/analysis runs, browse stored JDs, view resume gap report."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# `streamlit run ui/app.py` puts ui/ on sys.path, not the project root — add the root
# so `from config...` / `from db...` etc. resolve the same way they do for main.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from config.settings import DEFAULT_TARGET_COMPANIES, RESUME_FILE_PATH
from db.database import get_session, init_db
from db.repository import get_all_postings_with_analysis, save_resume_snapshot
from graph.workflow import build_workflow
from resume_loader import ResumeLoadError, load_resume_text

logging.basicConfig(level=logging.INFO)

st.set_page_config(page_title="Career Sniper", layout="wide")
init_db()

st.title("Career Sniper")
st.caption("Anthropic · Google · Salesforce · Palantir · OpenAI JD 분석 및 이력서 매칭")

with st.sidebar:
    st.header("실행")
    companies = st.multiselect("크롤링할 회사", DEFAULT_TARGET_COMPANIES, default=DEFAULT_TARGET_COMPANIES)
    run_button = st.button("크롤링 + 분석 실행", type="primary")

    if run_button:
        try:
            resume_text = load_resume_text(RESUME_FILE_PATH)
        except ResumeLoadError as exc:
            st.error(str(exc))
        else:
            with get_session() as session:
                save_resume_snapshot(session, RESUME_FILE_PATH, resume_text)

            workflow = build_workflow()
            initial_state = {
                "target_companies": companies,
                "resume_text": resume_text,
                "job_postings": [],
                "jd_analyses": [],
                "gap_analyses": [],
                "appeal_strategies": [],
                "errors": [],
            }
            with st.spinner("크롤링 및 분석 실행 중..."):
                final_state = workflow.invoke(initial_state)

            st.success(
                f"완료: 공고 {len(final_state.get('job_postings', []))}건, "
                f"추천 {len(final_state.get('appeal_strategies', []))}건"
            )
            for error in final_state.get("errors", []):
                st.warning(error)

st.header("저장된 채용공고")

with get_session() as session:
    postings = get_all_postings_with_analysis(session)

if not postings:
    st.info("아직 크롤링된 공고가 없습니다. 왼쪽에서 실행해보세요.")
else:
    company_filter = st.selectbox("회사 필터", ["전체"] + sorted({p.company for p in postings}))
    filtered = [p for p in postings if company_filter == "전체" or p.company == company_filter]

    for posting in filtered:
        gap = posting.gap_analysis
        strategy = posting.appeal_strategy
        score_label = f" · 매치 스코어 {gap.match_score:.0%}" if gap else ""

        with st.expander(f"[{posting.company}] {posting.title}{score_label}"):
            st.markdown(f"[공고 원문 보기]({posting.url})")
            preview = posting.jd_text[:1000] + ("..." if len(posting.jd_text) > 1000 else "")
            st.text(preview)

            if posting.jd_analysis:
                st.subheader("JD 분석")
                st.markdown(f"**핵심 역량**: {', '.join(posting.jd_analysis.core_competencies) or '-'}")
                st.markdown(f"**기술 스택**: {', '.join(posting.jd_analysis.tech_stack) or '-'}")
                st.markdown(f"**경력 요구사항**: {posting.jd_analysis.experience_requirements or '-'}")

            if gap:
                st.subheader("이력서 갭 분석")
                st.progress(min(max(gap.match_score, 0.0), 1.0))
                st.markdown(f"**일치하는 부분**: {', '.join(gap.matched_points) or '-'}")
                st.markdown(f"**부족한 부분**: {', '.join(gap.missing_points) or '-'}")

            if strategy:
                st.subheader(f"수정 추천 (우선순위: {strategy.priority})")
                for suggestion in strategy.resume_edit_suggestions:
                    st.markdown(f"- {suggestion}")
