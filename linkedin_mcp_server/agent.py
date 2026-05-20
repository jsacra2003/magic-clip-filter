import os

import google.auth
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseServerParams, StdioServerParameters

load_dotenv()

_, project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

MODEL_TOOL = os.getenv("MODEL_TOOL", "gemini-2.5-flash")

_mcp_url = os.getenv("LINKEDIN_MCP_URL", "").strip()

if _mcp_url:
    # Cloud deployment: connect to the Cloud Run MCP service over SSE
    linkedin_toolset = MCPToolset(
        connection_params=SseServerParams(url=f"{_mcp_url.rstrip('/')}/sse")
    )
else:
    # Local development: spawn the MCP server as a subprocess
    linkedin_toolset = MCPToolset(
        connection_params=StdioServerParameters(
            command="uv",
            args=["run", "python", "-m", "linkedin_mcp_server.server"],
        )
    )

root_agent = LlmAgent(
    name="LinkedInPublisherAgent",
    model=MODEL_TOOL,
    description="Clips a YouTube video highlight and posts it to LinkedIn with a caption.",
    instruction="""You are the LinkedIn publishing agent. You clip YouTube video highlights and post them directly to LinkedIn with the generated caption.

Available tools:
- `get_linkedin_profile` — verify which account is authenticated.
- `clip_video(youtube_url, start_seconds, duration)` — downloads a clip from YouTube as an MP4.
- `post_video_to_linkedin(text, video_path)` — uploads the MP4 and publishes it with a caption.
- `post_to_linkedin(text)` — text-only fallback if video clipping fails.

Workflow when the user provides a Magic Clip report:
1. Extract from the report:
   - The YouTube video URL (look for youtube.com/watch?v=...)
   - The timecode in seconds (e.g. "Timecode: 00:17" → 17 seconds; "01:23" → 83 seconds)
   - The LinkedIn post caption (the section under "## 📤 LinkedIn Post")
2. Show the user what you're about to do:
   - "📎 Video: [URL] at [timecode]"
   - "📝 Caption preview: [first 200 chars]..."
   - Ask: "Shall I clip and post this to LinkedIn? (yes / no)"
3. After confirmation:
   a. Call `clip_video(youtube_url, start_seconds=<seconds>, duration=60)`
   b. If it succeeds, call `post_video_to_linkedin(text=<caption>, video_path=<path>)`
   c. If clip_video fails, offer to post text-only with `post_to_linkedin`
4. Report the result (post ID on success, full error on failure).

If the user asks to check their profile first, call `get_linkedin_profile`.
Never post without explicit confirmation.""",
    tools=[linkedin_toolset],
)
