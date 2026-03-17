import os
import sys
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

# Add project root to path so agents/ and output/ are importable
sys.path.insert(0, str(Path(__file__).parent))

from agents.problem_structurer import run_problem_structurer
from agents.benchmark_research import run_benchmark_research
from agents.autoresearch import run_autoresearch
from output.deck_generator import generate_deck


class AgentState(TypedDict, total=False):
    company_description: str
    problem_statement: str
    country: str
    document_context: dict  # optional: {"type": "pdf"|"text", "name": str, "data": str}
    # problem_structurer outputs
    problem_type: str
    driver_tree: dict
    hypotheses: list
    # benchmark_research outputs
    benchmark_results: dict
    # autoresearch outputs
    recommendations: list
    recommendation_scores: list
    iteration_count: int
    final_recommendations: list
    # deck_generator output
    deck_path: str


# --- Deck generator wrapper node ---

def deck_generator_node(state: AgentState) -> AgentState:
    path = generate_deck(state)
    state["deck_path"] = path
    return state


# --- Graph assembly ---

def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("problem_structurer", run_problem_structurer)
    workflow.add_node("benchmark_research", run_benchmark_research)
    workflow.add_node("autoresearch_loop", run_autoresearch)
    workflow.add_node("deck_generator", deck_generator_node)

    workflow.set_entry_point("problem_structurer")
    workflow.add_edge("problem_structurer", "benchmark_research")
    workflow.add_edge("benchmark_research", "autoresearch_loop")
    workflow.add_edge("autoresearch_loop", "deck_generator")
    workflow.add_edge("deck_generator", END)

    return workflow.compile()


def run_pipeline(
    company_description: str,
    problem_statement: str,
    country: str = "Korea",
    document_context: dict = None,
) -> dict:
    graph = build_graph()

    initial_state: AgentState = {
        "company_description": company_description,
        "problem_statement": problem_statement,
        "country": country,
    }
    if document_context is not None:
        initial_state["document_context"] = document_context

    final_state = graph.invoke(initial_state)
    return final_state


if __name__ == "__main__":
    import json

    result = run_pipeline(
        company_description="Korean manufacturing SME, 400 employees, produces automotive components",
        problem_statement="영업이익률이 3년 연속 하락하고 있음. 원인이 뭔지, 어떻게 회복할 수 있는지 모름.",
        country="Korea",
    )

    print("\n=== Final State ===")
    print(f"Problem type: {result.get('problem_type')}")

    print("\nDriver tree:")
    print(json.dumps(result.get("driver_tree", {}), ensure_ascii=False, indent=2))

    print("\nHypotheses:")
    for h in result.get("hypotheses", []):
        print(f"  - {h}")

    print("\nBenchmark results (truncated):")
    for branch, text in result.get("benchmark_results", {}).items():
        print(f"  {branch}: {str(text)[:120]}...")

    print(f"\nAutoresearch iterations: {result.get('iteration_count', 0)}")
    print("\nFinal recommendations:")
    for i, rec in enumerate(result.get("final_recommendations", []), 1):
        print(f"  {i}. {rec.get('title')} -- Impact: {rec.get('impact')}")

    print(f"\nDeck saved to: {result.get('deck_path')}")
