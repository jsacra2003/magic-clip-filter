"""LinkedIn MCP Server — exposes LinkedIn posting as MCP tools.

Run once to authenticate:
    uv run python -m linkedin_mcp_server.auth

Then this server is started automatically by the ADK MCPToolset.
"""
import hashlib
import os
import subprocess
import tempfile
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from google.cloud import firestore
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("LinkedIn Publisher")

_LI_VERSION = "202501"
_LI_HEADERS_BASE = {
    "LinkedIn-Version": _LI_VERSION,
    "X-Restli-Protocol-Version": "2.0.0",
}
_FIRESTORE_COLLECTION = "linkedin_posts"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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


def _auth_headers(access_token: str) -> dict:
    return {**_LI_HEADERS_BASE, "Authorization": f"Bearer {access_token}"}


_db_client: firestore.Client | None = None

def _db() -> firestore.Client:
    global _db_client
    if _db_client is None:
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        _db_client = firestore.Client(project=project)
    return _db_client


def _doc_id(video_url: str) -> str:
    """Stable, safe Firestore document ID derived from the YouTube URL."""
    return hashlib.sha256(video_url.encode()).hexdigest()[:40]


def _check_duplicate(video_url: str) -> tuple[bool, str]:
    """Returns (is_duplicate, human-readable reason)."""
    try:
        doc = _db().collection(_FIRESTORE_COLLECTION).document(_doc_id(video_url)).get()
        if doc.exists:
            data = doc.to_dict()
            posted_at = data.get("posted_at", "unknown date")
            post_id = data.get("linkedin_post_id", "unknown")
            trend = data.get("trend", "unknown trend")
            return True, (
                f"⚠️ Duplicate detected: this video was already posted on {posted_at} "
                f"(trend: '{trend}', LinkedIn Post ID: {post_id})"
            )
    except Exception as exc:
        # Firestore unavailable — log and allow the post rather than blocking
        print(f"[firestore] duplicate check skipped: {exc}")
    return False, ""


def _record_post(video_url: str, trend: str, post_id: str, text: str) -> None:
    try:
        _db().collection(_FIRESTORE_COLLECTION).document(_doc_id(video_url)).set({
            "video_url": video_url,
            "trend": trend,
            "linkedin_post_id": post_id,
            "post_text_hash": hashlib.sha256(text.encode()).hexdigest(),
            "posted_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        print(f"[firestore] failed to record post: {exc}")


def _upload_video(access_token: str, author_urn: str, video_path: str) -> str:
    """Uploads a local MP4 to LinkedIn and returns the video URN."""
    file_size = os.path.getsize(video_path)

    init_resp = requests.post(
        "https://api.linkedin.com/rest/videos?action=initializeUpload",
        headers={**_auth_headers(access_token), "Content-Type": "application/json"},
        json={
            "initializeUploadRequest": {
                "owner": author_urn,
                "fileSizeBytes": file_size,
                "uploadCaptions": False,
                "uploadThumbnail": False,
            }
        },
        timeout=30,
    )
    init_resp.raise_for_status()
    upload_data = init_resp.json()["value"]

    video_urn = upload_data["video"]
    upload_token = upload_data["uploadToken"]
    instructions = upload_data["uploadInstructions"]

    uploaded_part_ids = []
    with open(video_path, "rb") as f:
        for instruction in instructions:
            first_byte = instruction["firstByte"]
            last_byte = instruction["lastByte"]
            f.seek(first_byte)
            chunk = f.read(last_byte - first_byte + 1)
            put_resp = requests.put(
                instruction["uploadUrl"],
                data=chunk,
                headers={"Content-Type": "application/octet-stream"},
                timeout=300,
            )
            put_resp.raise_for_status()
            uploaded_part_ids.append(put_resp.headers.get("ETag", "").strip('"'))

    finalize_resp = requests.post(
        "https://api.linkedin.com/rest/videos?action=finalizeUpload",
        headers={**_auth_headers(access_token), "Content-Type": "application/json"},
        json={
            "finalizeUploadRequest": {
                "video": video_urn,
                "uploadToken": upload_token,
                "uploadedPartIds": uploaded_part_ids,
            }
        },
        timeout=30,
    )
    finalize_resp.raise_for_status()
    return video_urn


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def check_if_already_posted(video_url: str) -> str:
    """Checks whether this YouTube video has already been posted to LinkedIn.

    Args:
        video_url: The YouTube video URL to check.

    Returns:
        A message stating whether the video was already posted (with date and
        LinkedIn Post ID) or has never been posted.
    """
    is_dup, reason = _check_duplicate(video_url)
    if is_dup:
        return reason
    return "✅ Not posted yet — safe to publish."


@mcp.tool()
def clip_video(youtube_url: str, start_seconds: int, duration: int = 60) -> str:
    """Downloads a clip from a YouTube video around a specific timestamp.

    Args:
        youtube_url: Full YouTube URL (e.g. https://www.youtube.com/watch?v=...).
        start_seconds: Highlight time in seconds (e.g. 17 for the 0:17 mark).
                       The clip starts 5 s before this for context.
        duration: Total clip length in seconds (default 60).

    Returns:
        Absolute path to the downloaded MP4 file, or an error message.
    """
    clip_start = max(0, start_seconds - 5)
    clip_end = clip_start + duration

    output_dir = tempfile.mkdtemp(prefix="magic_clip_")
    output_path = os.path.join(output_dir, "clip.mp4")

    cmd = [
        "yt-dlp",
        "--download-sections", f"*{clip_start}-{clip_end}",
        "--force-keyframes-at-cuts",
        "-f", "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]/mp4",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "-o", output_path,
        youtube_url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        return "Error: yt-dlp is not installed. Run: pip install yt-dlp"
    except subprocess.TimeoutExpired:
        return "Error: download timed out after 3 minutes."

    if result.returncode != 0:
        return f"yt-dlp error ({result.returncode}): {result.stderr[:400]}"

    if not os.path.exists(output_path):
        return f"Download finished but clip not found at {output_path}"

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    return f"{output_path}\nClip: {clip_start}s–{clip_end}s  ({size_mb:.1f} MB)"


@mcp.tool()
def post_to_linkedin(text: str, youtube_url: str = "", trend: str = "") -> str:
    """Publishes a text-only post to LinkedIn as the authenticated user.

    Checks Firestore for duplicates before posting and records the post after.

    Args:
        text: The ready-to-post content.
        youtube_url: The source YouTube URL (used for duplicate detection).
        trend: The trending topic this post is about (stored for reference).

    Returns:
        Success message with post ID, or an error / duplicate notice.
    """
    if youtube_url:
        is_dup, reason = _check_duplicate(youtube_url)
        if is_dup:
            return reason

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
        headers={**_auth_headers(access_token), "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )

    if resp.status_code == 201:
        post_id = resp.headers.get("x-restli-id", "unknown")
        if youtube_url:
            _record_post(youtube_url, trend, post_id, text)
        return f"✅ Posted to LinkedIn! Post ID: {post_id}"
    return f"❌ LinkedIn post failed ({resp.status_code}): {resp.text}"


@mcp.tool()
def post_video_to_linkedin(
    text: str, video_path: str, youtube_url: str = "", trend: str = ""
) -> str:
    """Uploads a local video clip and publishes it to LinkedIn with a caption.

    Checks Firestore for duplicates before posting and records the post after.
    Call clip_video first to obtain video_path.

    Args:
        text: Post caption text.
        video_path: Absolute path to a local MP4 file (returned by clip_video).
        youtube_url: The source YouTube URL (used for duplicate detection).
        trend: The trending topic this post is about (stored for reference).

    Returns:
        Success message with post ID and video URN, or an error / duplicate notice.
    """
    if youtube_url:
        is_dup, reason = _check_duplicate(youtube_url)
        if is_dup:
            return reason

    if not os.path.exists(video_path):
        return f"❌ Video file not found: {video_path}"

    access_token = _token()
    author_urn = _person_urn(access_token)

    try:
        video_urn = _upload_video(access_token, author_urn, video_path)
    except Exception as exc:
        return f"❌ Video upload failed: {exc}"

    payload = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {"media": {"id": video_urn}},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    resp = requests.post(
        "https://api.linkedin.com/rest/posts",
        headers={**_auth_headers(access_token), "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )

    if resp.status_code == 201:
        post_id = resp.headers.get("x-restli-id", "unknown")
        if youtube_url:
            _record_post(youtube_url, trend, post_id, text)
        return (
            f"✅ Video posted to LinkedIn!\n"
            f"Post ID: {post_id}\n"
            f"Video URN: {video_urn}"
        )
    return f"❌ LinkedIn video post failed ({resp.status_code}): {resp.text}"


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
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        mcp.run(transport="sse", host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
    else:
        mcp.run()
