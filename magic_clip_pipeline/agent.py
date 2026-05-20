import json
import os
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Optional

import requests
from pydantic import BaseModel

import google.auth
from dotenv import load_dotenv
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from agent04_media_check_agent.agent import check_pg16_content
from agent05_youtube_highlights_agent.tools import youtube_search
from google_trends_agent.tools import execute_bigquery_sql

load_dotenv()

_, project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

MODEL_AGENT = os.getenv("MODEL_AGENT", "gemini-2.5-pro")
MODEL_TOOL = os.getenv("MODEL_TOOL", "gemini-2.5-flash")


# --- Stage 1: Find trending topics ---

def get_trending_news(topic: str) -> str:
    """Fetches the top 10 trending news headlines for a given topic using Google News RSS.

    Args:
        topic: The subject or category to search for trending news (e.g. 'AI', 'NBA playoffs').

    Returns:
        A numbered list of the top trending headlines as a plain string.
    """
    encoded = urllib.parse.quote_plus(topic)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")[:10]
        headlines = []
        for i, item in enumerate(items, 1):
            title_el = item.find("title")
            title = title_el.text.strip() if title_el is not None and title_el.text else "No title"
            headlines.append(f"{i}. {title}")
        return "\n".join(headlines) if headlines else "No results found."
    except Exception as e:
        return f"Error fetching news: {e}"


trend_finder_agent = LlmAgent(
    name="TrendFinderAgent",
    model=MODEL_TOOL,
    description="Finds trending topics relevant to the user's query using Google News RSS or BigQuery Google Trends.",
    instruction="""You are a trend-discovery agent. Given the user's question, find the most relevant trending topics.

Rules:
- If the user mentions a specific category (tech, AI, sports, politics, entertainment, business, science, etc.):
  → Use the `get_trending_news` tool with that topic as the query.
  → Example: user says "tech news" → call get_trending_news(topic="technology AI")
- If the user asks about global trends with no specific category (e.g. "what's trending?", "top trends today"):
  → Use the `execute_bigquery_sql` tool with this query:
    SELECT term, rank FROM `bigquery-public-data.google_trends.top_terms` WHERE refresh_date = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY) ORDER BY rank ASC LIMIT 20

Return all results as-is. Do NOT summarize or pick yet — just output the raw list.""",
    tools=[get_trending_news, execute_bigquery_sql],
    output_key="trending_results",
)


# --- Stage 2: Extract the top trending term from the Trends output ---

trend_extractor_agent = LlmAgent(
    name="TrendExtractorAgent",
    model=MODEL_TOOL,
    description="Picks the most relevant trending term given the user's original request.",
    instruction="""You have two inputs:
1. The user's original question (at the top of the conversation).
2. The trending data from the previous agent in {trending_results} — a list of trending topics or headlines.

Your job: pick the SINGLE trending term or headline that best matches the topic or intent in the user's question.
- If the user asked about tech, sports, politics, etc. — pick the trending item closest to that domain.
- Prefer specific, concrete terms (e.g. "Apple WWDC 2025 announcement") over vague ones.
- If no item closely matches, pick the most newsworthy one.

Output ONLY the chosen term as a plain string. No punctuation, no explanation, no formatting.
Example output: OpenAI GPT-5 release""",
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


class SelectedVideo(BaseModel):
    video_id: str
    title: str
    url: str


# --- Stage 4: Select the best video ---

video_ranker_agent = LlmAgent(
    name="VideoRankerAgent",
    model=MODEL_AGENT,
    description="Selects the single best YouTube video for the trending topic.",
    instruction="""From the YouTube search results in the conversation, select the single best video that best represents the trending topic '{top_trend}'.

Pick the video most likely to contain a clear, watchable highlight moment related to the topic.""",
    output_schema=SelectedVideo,
    output_key="selected_video",
)


# --- Stage 5: Multimodal video analysis with vision callback ---

def _parse_video_from_state(raw) -> Optional[dict]:
    """Parses the selected_video state value into a dict, handling edge cases."""
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    # Strip markdown code fences if the model wrapped the JSON
    if text.startswith("```"):
        text = "\n".join(
            line for line in text.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _inject_video_into_request(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """Injects the selected video file into the LLM request for multimodal analysis."""
    raw = callback_context.state.get("selected_video")
    video = _parse_video_from_state(raw)
    if not video:
        return None

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


# --- Stage 7: Final report + social media export ---

social_export_agent = LlmAgent(
    name="SocialExportAgent",
    model=MODEL_AGENT,
    description="Compiles the Magic Clip Report and generates ready-to-post LinkedIn and Instagram content.",
    instruction="""You are compiling the final output of the Magic Clip pipeline. Using the data below, produce two things: the full report AND social media posts.

Trending topic: {top_trend}
Video highlight: {video_highlight}
PG-16 verdict: {pg16_verdict}

---

## 🔥 Trending Topic
State the trending topic in one sentence and why it matters right now.

## 🎬 Recommended Clip
List the video title, timecode, and the direct timestamped link. Include the one-sentence explanation of what happens at that moment.

## ✅ PG-16 Content Check
State the verdict clearly (APPROVED or FLAGGED) and the reason in one line.

## 📋 Summary
2-3 sentences summarising the full pipeline output.

---

## 📤 LinkedIn Post
Write a professional LinkedIn post (150–250 words) about this trending topic and clip.
- Hook with an insight or surprising fact from the video.
- Briefly explain why this trend matters for the industry.
- End with a thought-provoking question to drive comments.
- Include the timestamped clip link naturally in the text.
- Add 3–5 relevant hashtags at the bottom.

---

## 📸 Instagram Caption
Write an Instagram caption (80–120 words) for this clip.
- Start with an attention-grabbing opening line (no hashtags yet).
- Keep it conversational and energetic — Instagram audience skews younger.
- End with a call to action (e.g. "Link in bio", "Save this", "Tag someone who needs to see this").
- Add a line break then 10–15 relevant hashtags (mix of broad and niche).
""",
)


# --- Root Pipeline Agent ---

root_agent = SequentialAgent(
    name="MagicClipFilterPipeline",
    description=(
        "End-to-end pipeline: detects what's trending (via Google News RSS or BigQuery), "
        "finds the best YouTube clip for that trend, verifies PG-16 appropriateness, "
        "and generates ready-to-post LinkedIn and Instagram content."
    ),
    sub_agents=[
        trend_finder_agent,             # 1. Find trending topics (RSS for categories, BQ for global)
        trend_extractor_agent,          # 2. Extract top trending term
        youtube_search_for_trend_agent, # 3. Search YouTube for the trend
        video_ranker_agent,             # 4. Select best video
        video_highlight_agent,          # 5. Find highlight moment (multimodal)
        pg16_check_agent,               # 6. Verify PG-16 appropriateness
        social_export_agent,            # 7. Compile report + generate social posts
    ],
)
