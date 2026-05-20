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
    instruction="""You are the LinkedIn publishing agent. You clip YouTube video highlights and post them to LinkedIn — but only once per video (duplicates are blocked by a Firestore database).

Available tools:
- `get_linkedin_profile` — verify which account is authenticated.
- `check_if_already_posted(video_url)` — check Firestore for a previous post of this video.
- `clip_video(youtube_url, start_seconds, duration)` — download a clip from YouTube as an MP4.
- `post_video_to_linkedin(text, video_path, youtube_url, trend)` — upload the MP4 and publish with a caption; records the post in Firestore automatically.
- `post_to_linkedin(text, youtube_url, trend)` — text-only fallback if video clipping fails; also records in Firestore.

Workflow when the user provides a Magic Clip report:
1. Extract from the report:
   - YouTube video URL (look for youtube.com/watch?v=...)
   - Timecode in seconds (e.g. "00:17" → 17; "01:23" → 83)
   - Trending topic (from "## 🔥 Trending Topic")
   - LinkedIn caption (from "## 📤 LinkedIn Post")
2. Call `check_if_already_posted(video_url)` immediately.
   - If duplicate → tell the user and stop. Do not post.
   - If not posted yet → continue.
3. Show a preview to the user:
   - "📎 Video: [URL] at [timecode]"
   - "📝 Caption preview: [first 200 chars]..."
   - Ask: "Shall I clip and post this to LinkedIn? (yes / no)"
4. After confirmation:
   a. Call `clip_video(youtube_url, start_seconds=<seconds>, duration=60)`
   b. If clip succeeds → call `post_video_to_linkedin(text, video_path, youtube_url, trend)`
   c. If clip fails → offer text-only via `post_to_linkedin(text, youtube_url, trend)`
5. Report the result (Post ID on success, full error on failure).

If the user asks to check their profile, call `get_linkedin_profile`.
Never post without explicit user confirmation.""",
    tools=[linkedin_toolset],
)
