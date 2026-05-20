import json
import os
from typing import Any, Optional

import google.auth
from dotenv import load_dotenv
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from agent04_media_check_agent.agent import check_pg16_content
from agent05_youtube_highlights_agent.tools import youtube_search
from google_trends_agent.agent import root_agent as google_trends_root

load_dotenv()

_, project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

MODEL_AGENT = os.getenv("MODEL_AGENT", "gemini-2.5-pro")
MODEL_TOOL = os.getenv("MODEL_TOOL", "gemini-2.5-flash")


# --- Stage 2: Extract the top trending term from the Trends output ---

trend_extractor_agent = LlmAgent(
    name="TrendExtractorAgent",
    model=MODEL_TOOL,
    description="Extracts the single top trending term from the Google Trends results.",
    instruction="""Look at the Google Trends data produced by the previous agent.
Identify the single top trending term — the one with rank #1 or listed first.
Output ONLY that term as a plain string. No punctuation, no explanation, no formatting.
Example output: Mbappé hat trick""",
    output_key="top_trend",
)


# --- Stage 3: Search YouTube for the trending topic ---

youtube_search_for_trend_agent = LlmAgent(
    name="YouTubeSearchForTrendAgent",
    model=MODEL_TOOL,
    description="Searches YouTube for videos about the top trending topic.",
    instruction="""Use the `youtube_search` tool to find the 5 most relevant YouTube videos about: {top_trend}

Return the full list with video_id, title, and URL for each result.""",
    tools=[youtube_search],
    output_key="youtube_results",
)


# --- Stage 4: Select the best video ---

video_ranker_agent = LlmAgent(
    name="VideoRankerAgent",
    model=MODEL_AGENT,
    description="Selects the single best YouTube video for the trending topic.",
    instruction="""From the YouTube search results below, select the single best video that best captures the trending topic '{top_trend}'.

Search results:
{youtube_results}

Output ONLY a JSON object with these exact fields:
{{"video_id": "<id>", "title": "<title>", "url": "<full YouTube URL>"}}""",
    output_key="selected_video",
)


# --- Stage 5: Multimodal video analysis with vision callback ---

def _inject_video_into_request(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """Injects the selected video file into the LLM request for multimodal analysis."""
    raw = callback_context.state.get("selected_video")
    if not raw:
        return None

    video = raw if isinstance(raw, dict) else json.loads(raw)

    parts = [
        types.Part(text=f'Video title: {video["title"]}'),
        types.Part(text=f'Video URL: {video["url"]}'),
        types.Part(
            file_data=types.FileData(file_uri=video["url"], mime_type="video/*")
        ),
    ]
    video_content = types.Content(role="user", parts=parts)

    if llm_request.contents:
        llm_request.contents.insert(0, video_content)
    else:
        llm_request.contents = [video_content]

    return None


video_highlight_agent = LlmAgent(
    name="VideoHighlightAgent",
    model=MODEL_AGENT,
    description="Analyzes the selected video to find the key highlight moment.",
    instruction="""Analyze the YouTube video provided. Find the most relevant highlight moment for the trending topic: {top_trend}

Produce a structured report:
- **Video Title**: [title]
- **Timecode**: [MM:SS]
- **Direct Link**: [URL with ?t=Xs timestamp]
- **Confidence**: [X/10]
- **Explanation**: [what happens at this moment and why it represents the trend]""",
    before_model_callback=_inject_video_into_request,
    output_key="video_highlight",
)


# --- Stage 6: PG-16 content verification ---

pg16_check_agent = LlmAgent(
    name="PG16ContentCheckAgent",
    model=MODEL_TOOL,
    description="Verifies whether the trending topic and video are appropriate for PG-16 audiences.",
    instruction="""Check if the following content is appropriate for PG-16 audiences (under 16 years old).

Trending topic: {top_trend}
Selected video: {selected_video}

Use the `check_pg16_content` tool with the topic and video title.
Report the verdict clearly with ✅ APPROVED or ⚠️ FLAGGED and explain why.""",
    tools=[check_pg16_content],
    output_key="pg16_verdict",
)


# --- Stage 7: Final report ---

final_report_agent = LlmAgent(
    name="FinalReportAgent",
    model=MODEL_AGENT,
    description="Compiles the final Magic Clip Report.",
    instruction="""Compile a clean, structured **Magic Clip Report** combining all pipeline outputs.

Trending topic: {top_trend}
Video highlight: {video_highlight}
PG-16 verdict: {pg16_verdict}

Format the report with these sections:
## 🔥 Trending Topic
## 🎬 Recommended Clip
## ✅ PG-16 Content Check
## 📋 Summary

Make it concise and ready to share.""",
)


# --- Root Pipeline Agent ---

root_agent = SequentialAgent(
    name="MagicClipFilterPipeline",
    description=(
        "End-to-end pipeline: detects what's trending via Google Trends, "
        "finds the best YouTube clip for that trend, and verifies PG-16 appropriateness."
    ),
    sub_agents=[
        google_trends_root,             # 1+2. Generate SQL + execute → trending topics
        trend_extractor_agent,          # 3. Extract top trending term
        youtube_search_for_trend_agent, # 4. Search YouTube for the trend
        video_ranker_agent,             # 5. Select best video
        video_highlight_agent,          # 6. Find highlight moment (multimodal)
        pg16_check_agent,               # 7. Verify PG-16 appropriateness
        final_report_agent,             # 8. Compile final report
    ],
)
