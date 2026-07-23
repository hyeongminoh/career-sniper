"""Builds and compiles the LangGraph StateGraph wiring crawler -> jd_analyzer -> resume_matcher -> recommender."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.crawler_agent import crawler_agent
from agents.jd_analyzer_agent import jd_analyzer_agent
from agents.recommender_agent import recommender_agent
from agents.resume_matcher_agent import resume_matcher_agent
from graph.state import AgentState


def build_workflow() -> CompiledStateGraph:
    """Compiles the linear crawler -> jd_analyzer -> resume_matcher -> recommender graph."""
    graph = StateGraph(AgentState)

    graph.add_node("crawler", crawler_agent)
    graph.add_node("jd_analyzer", jd_analyzer_agent)
    graph.add_node("resume_matcher", resume_matcher_agent)
    graph.add_node("recommender", recommender_agent)

    graph.add_edge(START, "crawler")
    graph.add_edge("crawler", "jd_analyzer")
    graph.add_edge("jd_analyzer", "resume_matcher")
    graph.add_edge("resume_matcher", "recommender")
    graph.add_edge("recommender", END)

    return graph.compile()
