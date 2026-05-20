FROM python:3.12-slim
WORKDIR /app

# ffmpeg is required by yt-dlp for merging video+audio streams
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
# Stub packages so uv can resolve the workspace without the full source
RUN mkdir -p google_trends_agent agent04_media_check_agent \
             agent05_youtube_highlights_agent magic_clip_pipeline app && \
    touch google_trends_agent/__init__.py agent04_media_check_agent/__init__.py \
          agent05_youtube_highlights_agent/__init__.py magic_clip_pipeline/__init__.py \
          app/__init__.py

COPY linkedin_mcp_server/ ./linkedin_mcp_server/

RUN pip install --no-cache-dir uv==0.8.13 && \
    uv sync --no-dev --no-emit-project --locked

ENV MCP_TRANSPORT=sse
EXPOSE 8080

CMD ["uv", "run", "python", "-m", "linkedin_mcp_server.server"]
