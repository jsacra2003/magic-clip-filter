import os

from googleapiclient.discovery import build

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


def youtube_search(query: str) -> list:
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY not set.")
    youtube = build(
        YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=api_key
    )
    response = (
        youtube.search()
        .list(
            q=query, part="snippet", type="video", maxResults=5, videoEmbeddable="true"
        )
        .execute()
    )
    return [
        {
            "video_id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "url": f'https://www.youtube.com/watch?v={item["id"]["videoId"]}',
        }
        for item in response.get("items", [])
    ]
