import os
from typing import Any

from dotenv import load_dotenv
from google.adk.agents import LlmAgent

from agent04_media_check_agent.internal_helper_functions import (
    ADVERSE_KEYWORDS,
    _analyze_text_for_risks_utility,
    _make_google_search_request,
)

load_dotenv()

MODEL_AGENT = os.getenv("MODEL_AGENT", "gemini-2.5-pro")

PG16_RISK_KEYWORDS = [
    "explicit",
    "nsfw",
    "adult content",
    "18+",
    "rated r",
    "graphic violence",
    "gore",
    "horror",
    "sexual content",
    "nudity",
    "drug use",
    "strong language",
    "profanity",
    "disturbing",
    "hate speech",
    "self-harm",
    "suicide",
    "terrorist",
    "extremist",
]


def search_adverse_media_for_company_tool(
    entity_name: str,
    location_hint: str = "",
    site_filter: str = "",
) -> dict[str, Any]:
    """Searches for adverse media (fraud, lawsuits, scandals) about a company or entity.

    Args:
        entity_name: The company or entity name to search for.
        location_hint: Optional location context (e.g., "San Francisco").
        site_filter: Optional site to restrict search to (e.g., "reuters.com").

    Returns:
        Dict with entity_name, risks_found list, searches_performed count, and errors.
    """
    query_parts = [entity_name]
    if location_hint:
        query_parts.append(location_hint)
    if site_filter:
        query_parts.append(f"site:{site_filter}")
    base_query = " ".join(query_parts)

    all_risks = []
    errors = []
    searches_done = 0

    for keyword in ADVERSE_KEYWORDS[:6]:
        query = f"{base_query} {keyword}"
        results, error = _make_google_search_request(query, num_results=3)
        searches_done += 1

        if error:
            errors.append(error)
            continue

        if results:
            for item in results:
                snippet = item.get("snippet", "")
                url = item.get("link", "")
                risks = _analyze_text_for_risks_utility(snippet, entity_name, url)
                all_risks.extend(risks)

    return {
        "entity_name": entity_name,
        "risks_found": all_risks,
        "searches_performed": searches_done,
        "errors": errors,
    }


def check_pg16_content(topic: str, video_title: str = "") -> dict[str, Any]:
    """Verifies whether a topic or video is appropriate for PG-16 audiences (under 16).

    Scans the topic and title for mature content indicators, then performs a
    targeted Google search to surface any age-restriction signals.

    Args:
        topic: The trending topic or subject matter to evaluate.
        video_title: Optional YouTube video title for additional context.

    Returns:
        Dict with is_pg16_appropriate bool, verdict string, and flagged findings.
    """
    combined_text = f"{topic} {video_title}".lower()
    flagged_in_text = [kw for kw in PG16_RISK_KEYWORDS if kw in combined_text]

    query = f"{topic} age restriction mature content"
    results, _ = _make_google_search_request(query, num_results=3)

    search_flags = []
    if results:
        for item in results:
            snippet = item.get("snippet", "").lower()
            for kw in PG16_RISK_KEYWORDS:
                if kw in snippet:
                    search_flags.append(
                        {
                            "keyword": kw,
                            "source": item.get("link", ""),
                            "snippet": item.get("snippet", "")[:200],
                        }
                    )

    is_safe = len(flagged_in_text) == 0 and len(search_flags) == 0

    return {
        "topic": topic,
        "video_title": video_title,
        "is_pg16_appropriate": is_safe,
        "flagged_keywords_in_title": flagged_in_text,
        "search_findings": search_flags[:5],
        "verdict": "APPROVED for PG-16" if is_safe else "FLAGGED — may not be suitable for PG-16",
    }


root_agent = LlmAgent(
    name="AdverseMediaAndPG16CheckAgent",
    model=MODEL_AGENT,
    description="Checks for corporate adverse media (fraud, lawsuits, scandals) and verifies PG-16 content appropriateness.",
    instruction="""You are a content safety and adverse media specialist with two modes:

**Mode 1 — Adverse Media Check** (for companies/entities):
Use `search_adverse_media_for_company_tool` with the entity name, optional location, and optional site filter.
Summarize all risks found, grouped by keyword, with source links. End with a risk rating: Low / Medium / High.

**Mode 2 — PG-16 Content Check** (for trending topics or video content):
Use `check_pg16_content` with the topic and optional video title.
Report the verdict clearly:
- ✅ APPROVED for PG-16 — safe for audiences under 16
- ⚠️ FLAGGED — explain which keywords triggered the flag and why

Always be factual and cite the sources found. When in doubt, flag rather than approve.
""",
    tools=[search_adverse_media_for_company_tool, check_pg16_content],
)
