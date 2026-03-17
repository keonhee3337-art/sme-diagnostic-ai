import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent.parent / ".env")

SONNET_MODEL = "claude-sonnet-4-6"
HAIKU_MODEL = "claude-haiku-4-5-20251001"

GENERATION_SYSTEM = """You are a McKinsey senior consultant advising a Korean SME.
Based on the diagnostic data provided, generate 5 specific, actionable recommendations.

Output ONLY valid JSON — a list of exactly 5 objects:
[
  {
    "title": "<concise recommendation title>",
    "description": "<2-3 sentence explanation of what to do and why>",
    "impact": "<one of: high | medium | low>",
    "feasibility": "<one of: high | medium | low>"
  }
]

Rules:
- Recommendations must be grounded in the driver tree and benchmark data
- Each must be specific enough to act on within 90 days
- Feasibility must reflect what a Korean SME can realistically execute (budget, headcount, regulation)
- Output ONLY the JSON array. No markdown, no explanation."""

SCORING_SYSTEM = """You are a consulting quality reviewer.
Score each recommendation on 3 dimensions (0-10 each):
- relevance: does it address the root cause from the driver tree?
- specificity: is it concrete enough to act on?
- actionability: can a Korean SME realistically execute this?

Output ONLY valid JSON — a list of score objects, one per recommendation, in the same order:
[
  {"relevance": <0-10>, "specificity": <0-10>, "actionability": <0-10>}
]

Output ONLY the JSON array. No markdown, no explanation."""

IMPROVEMENT_SYSTEM = """You are a McKinsey senior consultant.
You are given a list of recommendations and their quality scores.
Improve the recommendations with scores below 7.5 average.
Keep recommendations with scores >= 7.5 unchanged.

Output ONLY valid JSON — the full list of 5 recommendations (improved where needed):
[
  {
    "title": "<concise recommendation title>",
    "description": "<2-3 sentence explanation of what to do and why>",
    "impact": "<one of: high | medium | low>",
    "feasibility": "<one of: high | medium | low>"
  }
]

Output ONLY the JSON array. No markdown, no explanation."""


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])
    return text.strip()


def _generate_recommendations(client: anthropic.Anthropic, state: dict) -> list[dict]:
    driver_tree = state.get("driver_tree", {})
    benchmark_results = state.get("benchmark_results", {})
    hypotheses = state.get("hypotheses", [])
    problem_type = state.get("problem_type", "unknown")

    user_message = (
        f"Problem type: {problem_type}\n\n"
        f"Driver tree:\n{json.dumps(driver_tree, ensure_ascii=False, indent=2)}\n\n"
        f"Hypotheses:\n" + "\n".join(f"- {h}" for h in hypotheses) + "\n\n"
        f"Benchmark findings:\n"
        + "\n".join(f"[{k}]: {v[:400]}" for k, v in benchmark_results.items())
    )

    response = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=2048,
        system=GENERATION_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )
    raw = _strip_fences(response.content[0].text)
    return json.loads(raw)


def _score_recommendations(
    client: anthropic.Anthropic, recommendations: list[dict], state: dict
) -> list[float]:
    driver_tree = state.get("driver_tree", {})
    problem_type = state.get("problem_type", "unknown")

    user_message = (
        f"Problem type: {problem_type}\n"
        f"Root cause: {driver_tree.get('root', 'unknown')}\n\n"
        f"Recommendations to score:\n"
        + json.dumps(recommendations, ensure_ascii=False, indent=2)
    )

    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=1024,
        system=SCORING_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )
    raw = _strip_fences(response.content[0].text)
    score_objects = json.loads(raw)

    averages = []
    for obj in score_objects:
        avg = (obj.get("relevance", 5) + obj.get("specificity", 5) + obj.get("actionability", 5)) / 3
        averages.append(round(avg, 2))
    return averages


def _improve_recommendations(
    client: anthropic.Anthropic,
    recommendations: list[dict],
    scores: list[float],
    state: dict,
) -> list[dict]:
    driver_tree = state.get("driver_tree", {})
    problem_type = state.get("problem_type", "unknown")

    annotated = []
    for rec, score in zip(recommendations, scores):
        annotated.append({**rec, "_avg_score": score, "_needs_improvement": score < 7.5})

    user_message = (
        f"Problem type: {problem_type}\n"
        f"Root cause: {driver_tree.get('root', 'unknown')}\n\n"
        f"Current recommendations with scores:\n"
        + json.dumps(annotated, ensure_ascii=False, indent=2)
        + "\n\nImprove recommendations where _needs_improvement is true. "
        "Return all 5, improved or not, without the _avg_score or _needs_improvement fields."
    )

    response = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=2048,
        system=IMPROVEMENT_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )
    raw = _strip_fences(response.content[0].text)
    improved = json.loads(raw)

    # Strip internal scoring fields in case model echoes them back
    cleaned = []
    for rec in improved:
        cleaned.append({
            "title": rec.get("title", ""),
            "description": rec.get("description", ""),
            "impact": rec.get("impact", "medium"),
            "feasibility": rec.get("feasibility", "medium"),
        })
    return cleaned


def run_autoresearch(state: dict) -> dict:
    """LangGraph node. Self-improving recommendation loop."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    iteration_count = state.get("iteration_count", 0)
    SCORE_THRESHOLD = 7.5
    MAX_ITERATIONS = 8

    # Step 1: Generate initial recommendations
    print(f"[autoresearch] Generating initial recommendations...")
    try:
        recommendations = _generate_recommendations(client, state)
    except (json.JSONDecodeError, KeyError, IndexError, Exception) as e:
        print(f"[autoresearch] Generation error: {e}. Using fallback.")
        recommendations = [
            {
                "title": f"Recommendation {i+1}",
                "description": "Further analysis required.",
                "impact": "medium",
                "feasibility": "medium",
            }
            for i in range(5)
        ]

    # Improvement loop
    while True:
        # Step 2: Score
        print(f"[autoresearch] Scoring recommendations (iteration {iteration_count})...")
        try:
            scores = _score_recommendations(client, recommendations, state)
        except (json.JSONDecodeError, KeyError, Exception) as e:
            print(f"[autoresearch] Scoring error: {e}. Using default scores.")
            scores = [5.0] * len(recommendations)

        avg_score = sum(scores) / len(scores) if scores else 0.0
        print(f"[autoresearch] Average score: {avg_score:.2f} | Iterations: {iteration_count}")

        # Step 3: Exit condition
        if avg_score >= SCORE_THRESHOLD or iteration_count >= MAX_ITERATIONS:
            print(f"[autoresearch] Done. Final avg score: {avg_score:.2f}, iterations: {iteration_count}")
            break

        # Step 4: Improve low-scoring recommendations
        print(f"[autoresearch] Improving recommendations below threshold...")
        try:
            recommendations = _improve_recommendations(client, recommendations, scores, state)
        except (json.JSONDecodeError, KeyError, Exception) as e:
            print(f"[autoresearch] Improvement error: {e}. Keeping current recommendations.")
            break

        iteration_count += 1

    state["recommendations"] = recommendations
    state["recommendation_scores"] = scores
    state["iteration_count"] = iteration_count
    state["final_recommendations"] = recommendations

    return state


if __name__ == "__main__":
    sample_state = {
        "company_description": "Korean manufacturing SME, 400 employees, produces automotive components",
        "problem_statement": "영업이익률이 3년 연속 하락하고 있음.",
        "country": "Korea",
        "problem_type": "operations",
        "driver_tree": {
            "root": "Declining operating margin",
            "branches": [
                {
                    "name": "Cost of Goods Sold",
                    "sub_branches": ["Raw material cost", "Labor cost"],
                },
                {
                    "name": "Revenue per Unit",
                    "sub_branches": ["Pricing power", "Customer mix"],
                },
                {
                    "name": "Operating Efficiency",
                    "sub_branches": ["Yield rate", "Overhead absorption"],
                },
            ],
        },
        "hypotheses": [
            "Hypothesis: Raw material cost increases are the primary driver of margin compression.",
            "Hypothesis: Pricing power has eroded due to increased competition from Chinese manufacturers.",
            "Hypothesis: Operational inefficiencies have worsened due to aging equipment.",
        ],
        "benchmark_results": {
            "Cost of Goods Sold": (
                "Korean auto parts manufacturers average COGS ratio of 72-75%. "
                "Raw material costs (steel, aluminum) increased 18% YoY in 2023. "
                "Labor costs in Korea rose 5.1% in 2023 per KEIS data."
            ),
            "Revenue per Unit": (
                "Average selling price for mid-tier auto components declined 3.2% as "
                "Hyundai/Kia pushed suppliers on cost reduction. Tier-2 suppliers face "
                "stronger pricing pressure than Tier-1 suppliers."
            ),
            "Operating Efficiency": (
                "Industry average OEE (Overall Equipment Effectiveness) for Korean auto parts "
                "is 68%. Top quartile achieves 82%+. Yield rates below 95% signal equipment "
                "issues. Smart factory adoption at 34% of mid-size manufacturers."
            ),
        },
    }

    result = run_autoresearch(sample_state)

    print("\n=== Final Recommendations ===")
    for i, rec in enumerate(result["final_recommendations"], 1):
        print(f"\n{i}. {rec['title']}")
        print(f"   {rec['description']}")
        print(f"   Impact: {rec['impact']} | Feasibility: {rec['feasibility']}")

    print(f"\n=== Scores ===")
    for i, score in enumerate(result["recommendation_scores"], 1):
        print(f"  Rec {i}: {score:.2f}")

    print(f"\nTotal iterations: {result['iteration_count']}")
