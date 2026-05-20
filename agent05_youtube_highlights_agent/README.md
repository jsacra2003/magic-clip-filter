# YouTube Highlights Agent

![agent arch](../img/youtube_highlight_agent_diagram.png)

## The Challenge
The objective of this agent is to create an Agent for a common but time-consuming task: finding specific moments or "highlights" within YouTube videos. In an era of abundant video content, users often need to find a key piece of information, a specific scene, or a summary of a long video without watching it in its entirety. Manually scrubbing through lengthy tutorials, lectures, reviews, or entertainment videos is inefficient and often frustrating.

The task is to build an agent that can take a user's query and a YouTube video, and automatically identify the most relevant segment. A successful solution will be able to handle a variety of use cases, including:
* **Efficient Learning:** Quickly finding the exact part of a tutorial that explains a specific concept.
* **Product Research:** Pinpointing the moment in a review where a particular feature is discussed or demonstrated.
* **Content Creation:** Easily locating highlight-worthy clips from longer videos for use in compilations or social media posts.
* **General Inquiry:** Answering questions about a video's content by finding the visual evidence that supports the answer.

The solution must be robust, reliable, and capable of delivering a precise, time-stamped answer to the user.

## Our Proposed Solution
The YouTube Highlights Agent is a multi-step AI agent designed to meet this challenge. It is a powerful tool that first finds relevant YouTube videos based on a user's query, allows for the selection of the best match, and then performs a deep, frame-by-frame analysis to pinpoint the exact moment that answers the user's question.

### Key Features
* **Targeted Search:** The agent uses the YouTube API to find a list of relevant videos based on the user's initial query.
* **Intelligent Ranking:** An LLM-based agent selects the single most promising video from the search results to ensure the analysis is focused and relevant.
* **Multimodal Analysis:** The agent leverages a powerful multimodal model to analyze the video's visual content, understanding objects, actions, and scenes.
* **Precise Timestamping:** The agent returns not just an explanation, but the exact timecode (in MM:SS format) where the relevant content can be found, along with a direct link to that moment in the video.
* **Confidence Scoring:** Provides a confidence score to indicate how certain the agent is about its finding based on the visual evidence.

## How it Works
The agent uses a sequential workflow, breaking the complex task into three distinct steps managed by specialized sub-agents:
1.  **Search:** The agent takes a natural language query from the user (e.g., "find the moment a car's interior is shown"). It uses the Youtube tool to query the YouTube API and retrieve a list of relevant videos.
2.  **Rank:** The agent analyzes the list of search results in the context of the user's original query and selects the single best video for analysis. This prevents wasted effort analyzing irrelevant content.
3.  **Analyze & Pinpoint:** The agent passes the selected video to a multimodal agent. It performs a visual analysis of the video content to find the precise moment that answers the user's query and generates a final report with the timestamped link and an explanation.

## System Architecture
The YouTube Highlights Agent operates as a sequential, tool-using AI agent. Its core architecture can be understood through the following components:
* **User Interface (UI):** The front end that accepts the user's query and displays the final report. This can be a command-line interface or a ADK/ Gemini enterprise web-based chat UI.
* **Root Agent (SequentialAgent):** The main agent that orchestrates the workflow by executing a series of sub-agents in a predefined order.
* **Sub-Agents (LlmAgent):**
    1.  **Youtube_agent:** The first agent in the sequence. It interprets the user's request and uses the Youtube tool to find videos.
    2.  **rank_agent:** The second agent. It receives the list of videos and uses its reasoning capabilities to select the single most relevant one.
    3.  **multimodal_agent:** The final agent. It receives the selected video and performs a visual analysis to identify the key moment and generate the answer.
* **Tool (FunctionTool):** The Youtube function is the primary tool. It abstracts the complexity of making API calls to the YouTube Data API.
* **APIs:**
    * **YouTube Data API v3:** Provides the underlying search functionality.
    * **Gemini API (Vertex AI):** Provides the LLM and multimodal models (gemini-2.5-pro, gemini-2.5-flash) that power the reasoning and analysis capabilities of the sub-agents.

### Data Flow:
1.  The user's query is passed to the Youtube_agent.
2.  The agent calls the Youtube tool, which queries the YouTube API.
3.  The search results are passed to the rank_agent.
4.  The rank_agent selects the best video and passes its URL to the multimodal_agent.
5.  The multimodal_agent analyzes the video using the Gemini API and identifies the key moment.
6.  The final, timestamped result is compiled into a clean, structured report for the user.

## Assignment
**Starter:** Code repo (the updated version to be shared during the hackathon in commonly accessible repo)

**High-level instructions:**
1.  Looking at the agent specification above and the provided code, implement an ADK agent.
2.  Test the agent locally (`uv run adk run agent` or `uv run adk web`).
3.  Deploy the agent to Agent Engine.
4.  Test the deployed version of the agent.
5.  Register the agent to Gemini Enterprise.
6.  Make sure it works in Gemini Enterprise as well.

**Example Prompts:**
* "Find the moment in a Cybertruck review where they show the interior"
* "When does the presenter in a 'Pixel 8 Pro' review talk about the camera?"
* "Show me the part of the MKBHD video that discusses the phone's battery life."

## Example input
"Find the moment in a Cybertruck review where they show the frunk"

## Example output
Video Analysis Report:
* **Video Title:** Tesla Cybertruck Review: Everything You Need To Know!
* **Video URL:** [https://www.youtube.com/watch?v=VIDEO_ID?&t=123s](https://www.youtube.com/watch?v=VIDEO_ID?&t=123s)
* **Timecode:** 02:03
* **Confidence:** 9/10
* **Explanation:** At this timecode, the presenter is standing in front of the Cybertruck and opens the front trunk (frunk), clearly displaying its size and features while discussing its capacity. This directly corresponds to the user's query.

## Setting up
To run the Agent Development Kit Application locally, we need to perform the following steps:
1.  Setup the Python virtual environment and install dependencies:
```bash

2. Add all necessary GCP Authentications and setup:

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

3. Make sure to have an .env file with the following variables setup:

```bash
GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
GOOGLE_CLOUD_LOCATION="us-central1" # e.g., us-central1 or europe-west1
GOOGLE_GENAI_USE_VERTEXAI="TRUE"
YOUTUBE_API_KEY="your_actual_youtube_api_key"
```

To get the YOUTUBE_API_KEY, you must enable the "YouTube Data API v3" in your GCP project.

In the Cloud Console, go to "APIs & Services" -> "Credentials." Click "Create Credentials" -> "API key." It is a best practice to restrict the API key to only the "YouTube Data API v3".

## High-level instructions
 - Use the tools above to come up with an agent, you can use the specification above for agent instruction
 - Test the agent locally (`uv run adk web`)
 - Deploy the agent to Agent Engine
 - Test the deployed version of the agent
 - Link the agent to a Gemini Enterprise application
 - Make sure it works in Gemini Enterprise as well
