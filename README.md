# SME Business Diagnostic AI

A multi-agent agentic AI system that transforms a free-text business problem into a structured consulting diagnosis and a 12-slide PowerPoint deck -- in minutes, not weeks.

Built for Korean SMEs. Designed to replicate the diagnostic rigor of McKinsey, BCG, and Deloitte strategy engagements using LangGraph, Perplexity API, and Anthropic Claude.

---

## What It Does

A business owner types their problem in plain language -- Korean or English. The system automatically decomposes it into a MECE driver tree, pulls live industry benchmarks from Perplexity sonar-pro, runs an autoresearch loop to generate and iteratively improve five prioritized recommendations, and outputs a professional consulting deck ready to share with leadership.

No consultants. No templates to fill in. Just a problem statement and an answer.

---

## Architecture

```
Free-text problem input
        |
        v
[Problem Structurer] -- claude-sonnet-4-6 --> MECE driver tree + 5 hypotheses
        |
        v
[Benchmark Research] -- Perplexity sonar-pro --> industry data per driver branch
        |
        v
[Autoresearch Loop] -- claude-haiku (scorer) + claude-sonnet (improver) --> 5 ranked recommendations (max 8 iterations)
        |
        v
[Deck Generator] -- python-pptx --> 12-slide consulting deck
```

State flows through a LangGraph StateGraph -- each node receives the full state dict and returns it updated. The autoresearch loop scores all five recommendations and improves any below a 7.5/10 threshold before proceeding.

---

## Demo Case

**Company:** Korean manufacturing SME, 400 employees, produces automotive components for Hyundai and Kia.

**Problem statement:** "영업이익률이 3년 연속 하락하고 있음. 원인이 뭔지, 어떻게 회복할 수 있는지 모름."
(Operating margin has declined for three consecutive years. We do not know the root cause or how to recover.)

**Output:** 12-slide deck with root cause analysis, competitive benchmarks from live Perplexity search, five prioritized recommendations ranked by impact and feasibility, and a 30-day action plan.

---

## 12-Slide Deck Structure

| Slide | Title | Content |
|-------|-------|---------|
| 1 | Title | Company name, problem statement, confidentiality footer |
| 2 | Executive Summary | Top 3 recommendations + key market finding |
| 3 | Problem Decomposition | MECE driver tree: root, branches, sub-branches |
| 4 | Hypotheses Investigated | 3-5 testable hypotheses from driver tree |
| 5 | Market Intelligence | Benchmark data for first 3 driver branches |
| 6 | Competitive Landscape | Benchmark data for remaining branches |
| 7 | Gap Analysis | Company position vs. industry benchmark per driver |
| 8 | Root Cause Analysis | Problem classification, core issue, supporting evidence |
| 9 | Recommendations | All 5 recommendations with impact and feasibility ratings |
| 10 | Implementation Roadmap | Phased timeline: H1 quick wins, H2 core, H3 strategic |
| 11 | ROI and Success Metrics | KPI targets and measurement cadence |
| 12 | Next Steps (30 Days) | 5 concrete actions from the top recommendation |

---

## Tech Stack

| Component | Purpose | Model / Library |
|-----------|---------|-----------------|
| LangGraph StateGraph | Multi-agent orchestration | langgraph>=0.2.0 |
| Problem Structurer | MECE decomposition, driver tree, hypotheses | claude-sonnet-4-6 |
| Benchmark Research | Live industry data per driver branch | Perplexity sonar-pro |
| Autoresearch Loop | Generate, score, improve recommendations | claude-sonnet-4-6 (generate/improve) + claude-haiku-4-5 (score) |
| Deck Generator | 12-slide consulting deck | python-pptx |
| Frontend | Streamlit UI -- no FastAPI, no uvicorn | streamlit |
| Environment | API key management | python-dotenv |

---

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API keys in your .env file
# ANTHROPIC_API_KEY=...
# PERPLEXITY_API_KEY=...

# 3. Launch the app
streamlit run app.py
```

The Streamlit UI runs locally. Enter your company description and problem statement in the sidebar, select the country, and click "Run Diagnostic".

---

## Business Context

Korean SMEs make up 99% of all businesses and employ 83% of the workforce in South Korea, yet most lack access to structured business diagnostics. A single McKinsey or BCG engagement costs tens of millions of Korean won and takes weeks. This system compresses the core analytical workflow -- problem framing, market benchmarking, hypothesis testing, recommendation generation -- into a pipeline that runs in under five minutes.

The autoresearch pattern (generate -> score -> improve -> iterate) is a general-purpose quality control mechanism applicable to any LLM output that benefits from iterative refinement. It is reusable across projects.

The system is designed to be extensible. DART FSS API integration (Korean corporate disclosure data) is planned as a next phase to add peer financial benchmarking for KOSPI/KOSDAQ companies.

---

## Author

**Keonhee Kim** -- SKKU Business Administration student, founder of SDC (SKKU-Deloitte Consulting) club.

Builds agentic AI systems at the intersection of business strategy and LLM engineering. Projects span LangGraph multi-agent pipelines, RAG with custom vector databases, Text2SQL, and MCP server development for Korean financial data (DART API).

GitHub: [github.com/keonhee3337-art](https://github.com/keonhee3337-art)

---

## Keywords

LangGraph, agentic AI, multi-agent system, Korean SME, consulting AI, MECE, driver tree, Perplexity API, python-pptx, autoresearch, BCG, McKinsey, business diagnostics, SKKU, Anthropic Claude, Streamlit, problem structuring, benchmark research, recommendation engine
