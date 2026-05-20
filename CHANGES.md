# Magic Clip Filter — Changes & Features Added

## Overview

Three agents were completed and a new pipeline orchestrator was created to wire them together into an end-to-end flow:

```
Google Trends → YouTube Clip Finder → PG-16 Content Check
```

---

## `agent05_youtube_highlights_agent` — YouTube Highlights Agent

### What changed
This agent was a skeleton with three `None` sub-agents and placeholder prompts.

### What was added

**`prompt.py`** — Replaced all three placeholder prompts with real instructions:
- `youtube_search_agent_prompt`: Instructs the agent to use `youtube_search` and return all 5 results without filtering.
- `rank_agent_prompt`: Instructs the model to select the single best video and output strict JSON (`video_id`, `title`, `url`).
- `multimodal_agent_prompt`: Instructs the multimodal model to watch the video, identify the key moment, and return a structured report with timecode, direct link, confidence score, and explanation.

**`agent.py`** — Implemented all four TODOs:

| Component | What it does |
|---|---|
| `RankedVideo` (Pydantic model) | Added fields: `video_id`, `title`, `url` |
| `search_tool_output_callback` | Stores search results and query in `tool_context.state` for downstream reuse |
| `rank_output_callback` | Parses the ranked video JSON from the model response and stores it in `callback_context.state["selected_video"]` |
| `vision_callback_builds_video_parts` | `before_model_callback` — reads `selected_video` from state, builds multimodal `Content` with the video's `file_data` URI, and injects it into the LLM request before the model call |
| `youtube_search_agent` | `LlmAgent` with `youtube_search` tool + `search_tool_output_callback` |
| `rank_agent` | `LlmAgent` with `output_schema=RankedVideo`, `output_key="selected_video"`, and `rank_output_callback` |
| `multimodal_agent` | `LlmAgent` with `vision_callback_builds_video_parts` as `before_model_callback` |
| `root_agent` | `SequentialAgent` with the three sub-agents in order |

**`__init__.py`** — Created (was missing).

---

## `agent04_media_check_agent` — Adverse Media & PG-16 Check Agent

### What changed
`agent.py` was `### TBA` — completely empty. The helper functions in `internal_helper_functions.py` already existed but had no agent wiring them together.

### What was added

**`agent.py`** — Full implementation:

| Component | What it does |
|---|---|
| `search_adverse_media_for_company_tool` | Wraps the existing helper functions: builds queries from entity name + optional location/site filter, runs up to 6 keyword searches via Google Custom Search API, scans snippets for adverse keywords, returns structured risk report |
| `check_pg16_content` | New tool for PG-16 verification. Scans topic + video title for 19 mature-content keywords (explicit, gore, adult content, etc.), then runs a Google Search for age-restriction signals. Returns `is_pg16_appropriate` bool + `verdict` string (APPROVED / FLAGGED) |
| `root_agent` | `LlmAgent` with both tools. Prompt handles two modes: adverse media check (corporate due diligence) and PG-16 content check (content suitability). Outputs ✅ APPROVED or ⚠️ FLAGGED with sourced reasoning |

---

## `magic_clip_pipeline` — End-to-End Pipeline Orchestrator *(new)*

### What it is
A new `SequentialAgent` that connects all three agents into a single automated pipeline.

### Architecture

```
Input: "What's trending in sports in Brazil today?"
    │
    ▼
[1] TrendsQueryGeneratorAgent    ← from google_trends_agent
    Generates BigQuery SQL for the user's region/topic
    │
    ▼
[2] TrendsQueryExecutorAgent     ← from google_trends_agent
    Executes SQL → returns top trending terms as markdown
    │  output_key: generated_sql (internal)
    ▼
[3] TrendExtractorAgent          ← new
    Extracts the single top trending term
    output_key: top_trend
    │
    ▼
[4] YouTubeSearchForTrendAgent   ← new, reuses youtube_search tool
    Searches YouTube for {top_trend}
    output_key: youtube_results
    │
    ▼
[5] VideoRankerAgent             ← new
    Selects best video for {top_trend} from {youtube_results}
    output_key: selected_video
    │
    ▼
[6] VideoHighlightAgent          ← new, multimodal
    Injects video via before_model_callback
    Identifies exact highlight moment (timecode, confidence, explanation)
    output_key: video_highlight
    │
    ▼
[7] PG16ContentCheckAgent        ← new, uses check_pg16_content tool
    Verifies {top_trend} + {selected_video} for PG-16 suitability
    output_key: pg16_verdict
    │
    ▼
[8] FinalReportAgent             ← new
    Compiles final Magic Clip Report with all outputs
    │
    ▼
Output: Markdown report with trending topic, timestamped clip link, PG-16 verdict
```

### Files created
- `magic_clip_pipeline/__init__.py`
- `magic_clip_pipeline/agent.py`
- `magic_clip_pipeline/.env.example`

### State flow
All agents share a single session state dict. The `output_key` on each `LlmAgent` writes the agent's output into state under that key. Subsequent agents reference prior values via `{key}` placeholders in their instructions — ADK substitutes these automatically in a `SequentialAgent`.

---

## `pyproject.toml` — Dependency & Package Updates

- Added `google-api-python-client` (required by `agent05_youtube_highlights_agent/tools.py` for the YouTube Data API)
- Added `requests` (required by `agent04_media_check_agent/internal_helper_functions.py` for the Google Custom Search API)
- Registered all new packages in `[tool.hatch.build.targets.wheel]`: `agent04_media_check_agent`, `agent05_youtube_highlights_agent`, `magic_clip_pipeline`

---

## Running the Pipeline

```bash
# Install dependencies
uv sync --dev

# Run the full pipeline via ADK web UI
uv run adk web

# Then select "MagicClipFilterPipeline" from the dropdown and enter a prompt like:
# "What's trending globally today?"
```

### Required environment variables
Copy `.env.example` to `.env` and fill in:
- `GOOGLE_CLOUD_PROJECT` — your GCP project ID
- `YOUTUBE_API_KEY` — YouTube Data API v3 key
- `GOOGLE_SEARCH_API_KEY` + `GOOGLE_CSE_ID` — for PG-16 / adverse media checks
