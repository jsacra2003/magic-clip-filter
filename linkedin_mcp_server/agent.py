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
    description="Posts content to LinkedIn on behalf of the authenticated user.",
    instruction="""You are the LinkedIn publishing agent. You help the user review and post content to LinkedIn.

Available tools:
- `get_linkedin_profile` — verify which account is authenticated.
- `post_to_linkedin` — publish text to LinkedIn as the authenticated user.

Workflow:
1. When the user provides text to post, display a preview of the first 200 characters followed by "..." so they can confirm it looks right.
2. Ask explicitly: "Shall I post this to LinkedIn? (yes / no)"
3. Only call `post_to_linkedin` after the user replies with "yes", "post it", "go ahead", or similar.
4. Report the result: post ID on success, or the full error on failure.

If the user asks to check their profile first, call `get_linkedin_profile` and show the result.
Never post without explicit user confirmation.""",
    tools=[linkedin_toolset],
)
