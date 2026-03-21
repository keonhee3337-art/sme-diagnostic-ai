import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent.parent / ".env")

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar-pro"


def _query_perplexity(query: str) -> str:
    """Run a single Perplexity API call. Returns the response text."""
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        raise EnvironmentError("PERPLEXITY_API_KEY not found in environment.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": [{"role": "user", "content": query}],
        "max_tokens": 1024,
    }

    response = requests.post(PERPLEXITY_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def run_benchmark_research(state: dict) -> dict:
    """LangGraph node. Queries Perplexity for each driver tree branch."""
    driver_tree = state.get("driver_tree", {})
    branches = driver_tree.get("branches", [])
    country = state.get("country", "Korea")

    benchmark_results = {}

    # TODO: dart-fss peer comparison for Korean companies

    industry = state.get("industry", "")
    revenue = state.get("revenue_krw", "")
    employees = state.get("employee_count", 0)

    for i, branch in enumerate(branches):
        branch_name = branch.get("name", f"branch_{i}")
        query = f"{branch_name} benchmark data: industry average, trend, competitive landscape"
        if industry:
            query += f" for {industry} companies"
        if revenue:
            query += f" with annual revenue around {revenue}"
        elif employees:
            query += f" with {employees} employees"
        if country == "Korea":
            query += " in Korea"

        print(f"[benchmark_research] Querying: {branch_name}")
        try:
            result = _query_perplexity(query)
            benchmark_results[branch_name] = result
        except Exception as e:
            print(f"[benchmark_research] Error on '{branch_name}': {e}")
            benchmark_results[branch_name] = f"Error: {e}"

        if i < len(branches) - 1:
            time.sleep(1)

    state["benchmark_results"] = benchmark_results
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
        "hypotheses": [],
    }

    result = run_benchmark_research(sample_state)

    print("\n=== Benchmark Results ===")
    for branch, text in result["benchmark_results"].items():
        print(f"\n--- {branch} ---")
        print(text[:400])
