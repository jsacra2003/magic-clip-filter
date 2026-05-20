"""LinkedIn MCP Server — exposes LinkedIn posting as MCP tools.

Run once to authenticate:
    uv run python -m linkedin_mcp_server.auth

Then this server is started automatically by the ADK MCPToolset.
"""
import os

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("LinkedIn Publisher")


def _token() -> str:
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "LINKEDIN_ACCESS_TOKEN is not set. Run 'make linkedin-auth' first."
        )
    return token


def _person_urn(access_token: str) -> str:
    resp = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    sub = resp.json().get("sub")
    if not sub:
        raise ValueError("Could not retrieve LinkedIn user ID from /v2/userinfo.")
    return f"urn:li:person:{sub}"


@mcp.tool()
def post_to_linkedin(text: str) -> str:
    """Publishes a text post to LinkedIn as the authenticated user.

    Args:
        text: The ready-to-post content. Will be published as-is.

    Returns:
        Success message with post ID, or an error description.
    """
    access_token = _token()
    author_urn = _person_urn(access_token)

    payload = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    resp = requests.post(
        "https://api.linkedin.com/rest/posts",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "LinkedIn-Version": "202501",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        json=payload,
        timeout=15,
    )

    if resp.status_code == 201:
        post_id = resp.headers.get("x-restli-id", "unknown")
        return f"✅ Posted to LinkedIn! Post ID: {post_id}"
    return f"❌ LinkedIn post failed ({resp.status_code}): {resp.text}"


@mcp.tool()
def get_linkedin_profile() -> str:
    """Returns the authenticated user's LinkedIn profile (name, email, ID).

    Returns:
        Formatted string with name, email and LinkedIn member ID.
    """
    access_token = _token()
    resp = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return (
        f"Name: {data.get('name', 'N/A')}\n"
        f"Email: {data.get('email', 'N/A')}\n"
        f"LinkedIn ID: {data.get('sub', 'N/A')}"
    )


if __name__ == "__main__":
    mcp.run()
