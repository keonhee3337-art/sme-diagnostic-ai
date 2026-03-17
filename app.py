import os
import base64
import sys
from pathlib import Path

from dotenv import load_dotenv

for _p in [Path(__file__).parent / '.env', Path(__file__).parent.parent / '.env', Path(__file__).parent.parent.parent / '.env']:
    if _p.exists():
        load_dotenv(dotenv_path=_p)
        break

import streamlit as st

# Add project root to sys.path so graph imports work
sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(
    page_title="SME Business Diagnostic AI",
    page_icon="📊",
    layout="wide",
)

# --- Sidebar ---
with st.sidebar:
    st.header("Company Input")

    company_description = st.text_area(
        "Company Description",
        placeholder="e.g. Korean manufacturing SME, 400 employees, produces automotive components for Hyundai and Kia",
        height=120,
    )

    problem_statement = st.text_area(
        "Problem Statement",
        placeholder="e.g. 영업이익률이 3년 연속 하락하고 있음. 원인이 뭔지, 어떻게 회복할 수 있는지 모름.",
        height=120,
    )

    country = st.selectbox("Country", options=["Korea", "Other"])

    uploaded_file = st.file_uploader(
        "Attach Document (optional)",
        type=["txt", "md", "pdf"],
        help="Upload a company report, financial statement, or any relevant document. Content is passed as context to the AI.",
    )

    run_button = st.button("Run Diagnostic", type="primary", use_container_width=True)

# --- Main area ---
st.title("SME Business Diagnostic AI")
st.caption("Multi-agent consulting pipeline — Problem Decomposition | Benchmark Research | Autoresearch | Deck Generation")

# Run pipeline on button click
if run_button:
    if not company_description.strip():
        st.error("Company Description is required.")
        st.stop()
    if not problem_statement.strip():
        st.error("Problem Statement is required.")
        st.stop()

    # Extract document context from uploaded file
    document_context = None
    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        if uploaded_file.type == "application/pdf":
            # Pass as base64 for Claude's document API
            document_context = {
                "type": "pdf",
                "name": uploaded_file.name,
                "data": base64.standard_b64encode(file_bytes).decode("utf-8"),
            }
        else:
            # Plain text / markdown
            try:
                document_context = {
                    "type": "text",
                    "name": uploaded_file.name,
                    "data": file_bytes.decode("utf-8"),
                }
            except UnicodeDecodeError:
                st.warning("Could not read the uploaded file as text. Proceeding without document context.")

    with st.spinner("Running diagnostic pipeline..."):
        try:
            from graph import run_pipeline
            result = run_pipeline(company_description, problem_statement, country, document_context)
            st.session_state["diagnostic_result"] = result
            st.session_state["run_complete"] = True
            st.session_state["followup_history"] = []
        except Exception as e:
            st.error(f"Pipeline error: {str(e)}")
            st.info("Check that ANTHROPIC_API_KEY and PERPLEXITY_API_KEY are set in your .env file.")
            st.stop()

# Display results if available
if st.session_state.get("run_complete") and "diagnostic_result" in st.session_state:
    result = st.session_state["diagnostic_result"]

    st.success("Diagnostic complete. Deck ready for download.")

    # Phase 1: Problem Decomposition
    with st.expander("Problem Decomposition", expanded=False):
        driver_tree = result.get("driver_tree", {})
        root = driver_tree.get("root", "N/A")
        branches = driver_tree.get("branches", [])
        problem_type = result.get("problem_type", "N/A")

        st.markdown(f"**Problem Type:** {problem_type.upper()}")
        st.markdown(f"**Root:** {root}")
        st.markdown("")

        for branch in branches:
            st.markdown(f"- **{branch.get('name', '')}**")
            for sub in branch.get("sub_branches", []):
                st.markdown(f"  - {sub}")

        hypotheses = result.get("hypotheses", [])
        if hypotheses:
            st.markdown("")
            st.markdown("**Hypotheses:**")
            for h in hypotheses:
                st.markdown(f"- {h}")

    # Phase 2: Benchmark Research
    with st.expander("Benchmark Research", expanded=False):
        benchmark_results = result.get("benchmark_results", {})
        if benchmark_results:
            for branch_name, text in benchmark_results.items():
                st.markdown(f"**{branch_name}**")
                st.markdown(text)
                st.markdown("")
        else:
            st.write("No benchmark data available.")

    # Phase 3: Recommendations
    with st.expander("Recommendations", expanded=True):
        final_recs = result.get("final_recommendations", [])
        scores = result.get("recommendation_scores", [])
        iterations = result.get("iteration_count", 0)

        if final_recs:
            st.caption(f"Generated via autoresearch loop — {iterations} improvement iteration(s)")
            for i, rec in enumerate(final_recs, 1):
                score_str = ""
                if i - 1 < len(scores):
                    score_str = f" | Score: {scores[i-1]:.1f}/10"

                st.markdown(
                    f"**{i}. {rec.get('title', '')}**"
                    f"  —  Impact: `{rec.get('impact', 'medium').upper()}`"
                    f"  |  Feasibility: `{rec.get('feasibility', 'medium').upper()}`"
                    f"{score_str}"
                )
                st.markdown(rec.get("description", ""))
                st.markdown("")
        else:
            st.write("No recommendations generated.")

    # Phase 4: Deck download
    deck_path = result.get("deck_path")
    if deck_path and Path(deck_path).exists():
        with open(deck_path, "rb") as f:
            deck_bytes = f.read()
        st.download_button(
            label="Download Consulting Deck",
            data=deck_bytes,
            file_name="sme_diagnostic_deck.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    else:
        st.warning("Deck file not found. The pipeline may have completed but deck generation failed.")

    # ------------------------------------------------------------------
    # Follow-up Q&A
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("Ask a Follow-up Question")
    st.caption("Ask anything about this diagnosis — dive deeper into a recommendation, challenge an assumption, or explore a new direction.")

    # Display previous follow-up exchanges
    for exchange in st.session_state.get("followup_history", []):
        with st.chat_message("user"):
            st.write(exchange["question"])
        with st.chat_message("assistant"):
            st.markdown(exchange["answer"])

    followup_q = st.chat_input("Your follow-up question...")

    if followup_q:
        with st.chat_message("user"):
            st.write(followup_q)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    import anthropic as _anthropic

                    _client = _anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

                    # Build context summary from diagnostic result
                    recs_summary = "\n".join(
                        f"- {r.get('title', '')}: {r.get('description', '')[:120]}"
                        for r in result.get("final_recommendations", [])[:3]
                    )
                    driver_tree = result.get("driver_tree", {})
                    root_problem = driver_tree.get("root", "")
                    hypotheses = result.get("hypotheses", [])

                    context_block = (
                        f"Company: {result.get('company_description', '')}\n"
                        f"Problem: {result.get('problem_statement', '')}\n"
                        f"Root issue diagnosed: {root_problem}\n"
                        f"Problem type: {result.get('problem_type', 'unknown')}\n"
                        f"Key hypotheses: {'; '.join(hypotheses[:3])}\n"
                        f"Top recommendations:\n{recs_summary}"
                    )

                    # Include previous follow-up exchanges for continuity
                    messages = []
                    for ex in st.session_state.get("followup_history", []):
                        messages.append({"role": "user", "content": ex["question"]})
                        messages.append({"role": "assistant", "content": ex["answer"]})
                    messages.append({"role": "user", "content": followup_q})

                    response = _client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=1024,
                        system=(
                            "You are a McKinsey-trained consulting advisor. "
                            "Answer follow-up questions about the business diagnostic below. "
                            "Be specific, cite data from the diagnostic when relevant, and be concise.\n\n"
                            f"[Diagnostic Context]\n{context_block}"
                        ),
                        messages=messages,
                    )

                    answer = response.content[0].text
                    st.markdown(answer)

                    # Persist exchange
                    if "followup_history" not in st.session_state:
                        st.session_state["followup_history"] = []
                    st.session_state["followup_history"].append({
                        "question": followup_q,
                        "answer": answer,
                    })

                except Exception as e:
                    st.error(f"Follow-up error: {e}")
