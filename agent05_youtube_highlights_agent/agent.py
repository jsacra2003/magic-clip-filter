import json
import os
from typing import Any, Dict, Optional

import google.auth
from dotenv import load_dotenv
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from pydantic import BaseModel, HttpUrl

from .prompt import (
    multimodal_agent_prompt,
    rank_agent_prompt,
    youtube_search_agent_prompt,
)
from .tools import youtube_search


class RankedVideo(BaseModel):
    """Represents the video selected by the ranking agent."""

    video_id: str
    title: str
    url: str


def search_tool_output_callback(
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, tool_response: Dict
) -> Optional[Dict]:
    # Store for later reuse the user query and the youtube search result
    tool_context.state["search_results"] = tool_response
    tool_context.state["search_query"] = args.get("query", "")
    return None


def rank_output_callback(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    # Parse the selected video from the model response and store in state
    if llm_response.content and llm_response.content.parts:
        for part in llm_response.content.parts:
            text = getattr(part, "text", None)
            if text:
                try:
                    video_data = json.loads(text)
                    callback_context.state["selected_video"] = video_data
                    break
                except (json.JSONDecodeError, ValueError):
                    pass
    return None


def build_llm_parts(video):
    # Create parts for the llm call
    parts = []
    parts.append(types.Part(text=f'Video: {video["title"]}'))
    parts.append(types.Part(text=f'url: {video["url"]}'))
    parts.append(
        types.Part(file_data=types.FileData(file_uri=video["url"], mime_type="video/*"))
    )
    return parts


def vision_callback_builds_video_parts(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    # Inject the selected video into the LLM request for multimodal analysis
    selected_video = callback_context.state.get("selected_video")
    if not selected_video:
        return None

    if isinstance(selected_video, str):
        try:
            selected_video = json.loads(selected_video)
        except (json.JSONDecodeError, ValueError):
            return None

    video_parts = build_llm_parts(selected_video)
    video_content = types.Content(role="user", parts=video_parts)

    if llm_request.contents:
        llm_request.contents.insert(0, video_content)
    else:
        llm_request.contents = [video_content]

    return None


# Load environment variables from .env file
load_dotenv()

_, project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

MODEL_AGENT = os.getenv("MODEL_AGENT", "gemini-2.5-pro")
MODEL_TOOL = os.getenv("MODEL_TOOL", "gemini-2.5-flash")


youtube_search_agent = LlmAgent(
    name="YouTubeSearchAgent",
    model=MODEL_TOOL,
    description="Searches YouTube for videos relevant to the user's query.",
    instruction=youtube_search_agent_prompt,
    tools=[youtube_search],
    after_tool_callback=search_tool_output_callback,
)

rank_agent = LlmAgent(
    name="VideoRankAgent",
    model=MODEL_AGENT,
    description="Selects the single best YouTube video from the search results.",
    instruction=rank_agent_prompt,
    after_model_callback=rank_output_callback,
    output_schema=RankedVideo,
    output_key="selected_video",
)

multimodal_agent = LlmAgent(
    name="VideoHighlightAgent",
    model=MODEL_AGENT,
    description="Analyzes the selected video to pinpoint the key highlight moment.",
    instruction=multimodal_agent_prompt,
    before_model_callback=vision_callback_builds_video_parts,
)

root_agent = SequentialAgent(
    name="YouTubeHighlightsAgent",
    description="Finds a YouTube video for the user's query, selects the best match, and identifies the key highlight moment with a precise timestamp.",
    sub_agents=[youtube_search_agent, rank_agent, multimodal_agent],
)
