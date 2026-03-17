import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent.parent / ".env")

SYSTEM_PROMPT = """You are a McKinsey-trained business analyst. Given a company description and problem statement, you must output ONLY valid JSON with this exact structure:

{
  "problem_type": "<one of: market_entry | revenue | operations | product>",
  "driver_tree": {
    "root": "<the core problem in one phrase>",
    "branches": [
      {
        "name": "<branch name>",
        "sub_branches": ["<leaf>", "<leaf>", ...]
      }
    ]
  },
  "hypotheses": ["<hypothesis 1>", "<hypothesis 2>", ...]
}

Rules:
- driver_tree must have 3 levels (root → branches → sub_branches)
- branches: 3-4 items, each with 2-3 sub_branches (total 6-10 sub_branches across all branches)
- hypotheses: 3-5 testable statements starting with "Hypothesis:"
- All text can be in the same language as the problem_statement
- Output ONLY the JSON object. No markdown, no explanation."""


def run_problem_structurer(state: dict) -> dict:
    """LangGraph node. Takes state, returns updated state."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    text_content = (
        f"Company: {state['company_description']}\n"
        f"Country: {state.get('country', 'Korea')}\n"
        f"Problem: {state['problem_statement']}"
    )

    doc_ctx = state.get("document_context")
    if doc_ctx:
        if doc_ctx["type"] == "pdf":
            # Claude native PDF support via base64 document block
            content = [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": doc_ctx["data"],
                    },
                    "title": doc_ctx.get("name", "Attached document"),
                },
                {"type": "text", "text": text_content},
            ]
        else:
            # Plain text — prepend as additional context
            content = (
                f"{text_content}\n\n"
                f"[Attached document — {doc_ctx.get('name', 'document')}]\n"
                f"{doc_ctx['data'][:4000]}"  # cap at 4K chars
            )
    else:
        content = text_content

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        raw = response.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

        parsed = json.loads(raw)
        state["problem_type"] = parsed.get("problem_type", "unknown")
        state["driver_tree"] = parsed.get("driver_tree", {})
        state["hypotheses"] = parsed.get("hypotheses", [])

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"[problem_structurer] Parse error: {e}. Using fallback structure.")
        state["problem_type"] = "unknown"
        state["driver_tree"] = {
            "root": state["problem_statement"][:80],
            "branches": [
                {"name": "Revenue", "sub_branches": ["Price", "Volume"]},
                {"name": "Cost", "sub_branches": ["COGS", "SG&A"]},
                {"name": "External", "sub_branches": ["Market", "Competition"]},
            ],
        }
        state["hypotheses"] = ["Hypothesis: Further analysis required."]

    return state


if __name__ == "__main__":
    sample_state = {
        "company_description": "Korean manufacturing SME, 400 employees, produces automotive components",
        "problem_statement": "영업이익률이 3년 연속 하락하고 있음. 원인이 뭔지, 어떻게 회복할 수 있는지 모름.",
        "country": "Korea",
    }

    result = run_problem_structurer(sample_state)

    print("=== Problem Type ===")
    print(result["problem_type"])

    print("\n=== Driver Tree ===")
    print(json.dumps(result["driver_tree"], ensure_ascii=False, indent=2))

    print("\n=== Hypotheses ===")
    for h in result["hypotheses"]:
        print(f"  - {h}")
