import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple, TypedDict

import requests
from dotenv import load_dotenv

# --- Environment Variable Loading ---
load_dotenv()

# Note: You only need Google Search credentials for this version
# Read at call time (not import time) so Agent Engine env vars are picked up
GOOGLE_SEARCH_API_KEY = None
GOOGLE_CSE_ID = None

# --- Common Model Name (Update if needed) ---
MODEL_NAME = "gemini-2.5-pro"

# --- Global Constants & Configuration ---
ADVERSE_KEYWORDS = [
    "fraud",
    "scam",
    "bribery",
    "corruption",
    "money laundering",
    "sanction",
    "litigation",
    "lawsuit",
    "investigation",
    "regulatory action",
    "fine",
    "penalty",
    "misconduct",
    "allegation",
    "accusation",
    "complaint",
    "bankruptcy",
    "insolvency",
    "scandal",
    "controversy",
    "negative press",
    "environmental damage",
    "human rights abuse",
    "forced labor",
    "exploitation",
    "tax evasion",
    "criminal charges",
    "arrest",
    "conviction",
    "indictment",
    "aml breach",
    "regulatory fine",
    "community impact",
    "local protest",
    "planning dispute",
    "environmental spill",
    "job cuts controversy",
]
GOOGLE_SEARCH_BASE_URL = "https://www.googleapis.com/customsearch/v1"
REQUEST_TIMEOUT_SECONDS = 15


# --- TypedDict Definitions for Structured Data (Simplified) ---
class IdentifiedRisk(TypedDict):
    """Represents a single piece of identified adverse media."""

    entity_name: str
    keyword_triggered: str
    source_url: str
    snippet: str


# --- Internal API Client Helper Functions ---
def _make_google_search_request(
    query: str, num_results: int = 5
) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """Makes a request to the Google Custom Search API."""
    search_api_key = os.environ.get("GOOGLE_SEARCH_API_KEY")
    cse_id = os.environ.get("GOOGLE_CSE_ID")
    if not search_api_key or not cse_id:
        return None, "Google Search API Key or CSE ID is not configured."
    try:
        params = {
            "key": search_api_key,
            "cx": cse_id,
            "q": query,
            "num": num_results,
        }
        response = requests.get(
            GOOGLE_SEARCH_BASE_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return response.json().get("items", []), None
    except requests.exceptions.HTTPError as e:
        return (
            None,
            f"Google Search HTTP error for '{query}': {e}. Response: {e.response.text if e.response else 'N/A'}",
        )
    except requests.exceptions.RequestException as e:
        return None, f"Google Search request failed for '{query}': {e}"
    except json.JSONDecodeError as e:
        return None, f"Google Search JSON decode error for '{query}': {e}"


def _analyze_text_for_risks_utility(
    text_to_analyze: str, entity_name: str, source_url: str
) -> List[IdentifiedRisk]:
    """Scans a text snippet for adverse keywords and returns any identified risks."""
    found_risks: List[IdentifiedRisk] = []
    text_lower = text_to_analyze.lower()
    for keyword in ADVERSE_KEYWORDS:
        if keyword in text_lower:
            found_risks.append(
                IdentifiedRisk(
                    entity_name=entity_name,
                    keyword_triggered=keyword,
                    source_url=source_url,
                    snippet=text_to_analyze[:300] + "...",
                )
            )
    return found_risks


if __name__ == "__main__":
    # example of running a Google Search query
    search_res = _make_google_search_request(
        query="who is Ada Lovevlace?", num_results=1
    )
    print(search_res)

    # example of analyzing a snippet of text for risks
    example_text_to_analyze = """This company was involved in a fraud case and faced a significant fine due to regulatory action."""
    entity_name = "Example Corp"
    source_url = "https://example.com/news/fraud-case"
    found_risks = _analyze_text_for_risks_utility(
        example_text_to_analyze, entity_name, source_url
    )

    print(found_risks)
