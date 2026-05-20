# Adverse Media Check Agent

The Adverse Media is a highly configurable tool that performs targeted searches for adverse media concerning a specific company, leveraging natural language processing to identify potential reputational risks, legal issues, and other negative news from a wide array of public sources.

![agent architecture](../img/adverse_media_check_agent.jpg)

### Key Features

* **Targeted Searches**: The agent focuses on specific keywords related to fraud, corruption, legal disputes, and other risks to ensure relevant results.
* **Customizable Search Parameters**: Users can refine their search by specifying a company name, location hints, and specific websites to include.
* **Detailed Reporting**: The agent generates a concise, human-readable report summarizing its findings, complete with snippets of adverse media and direct links to the original sources.
* **Error Handling**: The agent provides clear feedback on any issues encountered during the search process, ensuring transparency and reliability.

### How it Works

The agent uses the Google Custom Search API to perform its searches.  Its workflow is designed to be straightforward and efficient:

1.  **Receive Input**: The agent takes a company name and optional location and site filters from the user.
2.  **Execute Search**: It uses a predefined list of keywords to search for adverse media.
3.  **Compile and Report**: The agent compiles its findings into a structured report and returns it to the user.

---

## System Architecture

The Adverse Media Checker operates as a tool-using AI agent. Its core architecture can be understood through the following components:

* **User Interface (UI)**: The front end that accepts user input (company name, location, filters) and displays the final report. This can be a simple command-line interface or a web-based chat UI.
* **LLM Agent**: The central component responsible for reasoning and planning. It interprets the user's request and decides which tools to use to fulfill it. The agent's core instruction is to "search for adverse media."
* **Tool**: A programmatic function available to the LLM. In this case, the `search_adverse_media_for_company_tool` is the primary tool. This tool abstracts away the complexities of making API calls and formatting search queries.
* **API**: The Google Custom Search API, which provides the underlying search functionality. The tool communicates with this API to retrieve search results from a wide range of public sources.
* **Data Flow**: The flow is a continuous loop:
    1.  The user's query is passed to the LLM Agent.
    2.  The LLM Agent, using its reasoning capabilities, determines that it needs to use the `search_adverse_media_for_company_tool`.
    3.  The tool is called with the user's input, which in turn makes a request to the Google Custom Search API.
    4.  The search results are returned to the tool, which then passes them back to the LLM Agent.
    5.  The LLM Agent processes the raw search results, extracts relevant snippets, and compiles them into a clean, structured report for the user.

##  Example Prompts

- Enron
- Wells Fargo in San Francisco
- Volkswagen site:reuters.com
- HSBC in Hong Kong site:wsj.com
- Samsung in South Korea

Example input:
```
Volkswagen site:reuters.com
```

Example output:

```
An adverse media check was performed on Volkswagen, with searches restricted to reuters.com.

**Adverse Media Findings:**

The following potential risks were identified:

- Keyword: lawsuit, Snippet: "Carmakers face UK dieselgate lawsuits worth at least $7.6 bln ... Jun 12, 2024 ... ... Volkswagen admitted to using "defeat devices" to change diesel vehicles' emissions levels during testing. Stay up to date with the latest news ......", Source: https://www.reuters.com/business/autos-transportation/carmakers-face-uk-dieselgate-lawsuits-worth-least-76-bln-lawyers-say-2024-06-11/
- Keyword: fine, Snippet: "Volkswagen, Stellantis and other carmakers hit with $495 million EU ... Apr 1, 2025 ... My News. Volkswagen, Stellantis and other carmakers hit with $495 million EU cartel fine. By Foo Yun Chee and Makini Brice. April 1, 202510:46 ......", Source: https://www.reuters.com/sustainability/boards-policy-regulation/eu-issues-458-million-euro-fine-car-manufacturers-over-vehicle-recycling-cartel-2025-04-01/
- Keyword: tax evasion, Snippet: "Exclusive: Volkswagen India unit faces $1.4 billion tax evasion ... Nov 29, 2024 ... Such imports were made by Volkswagen's India unit, Skoda Auto Volkswagen ... News about the alleged tax evasion comes at a time when the ......", Source: https://www.reuters.com/business/autos-transportation/volkswagen-india-unit-faces-14-billion-tax-evasion-notice-2024-11-29/

**Search Scope & Errors:**

The check involved 6 searches against different adverse media keywords. There were no errors during the search process.

**Conclusion:**

The search found significant adverse media related to Volkswagen on reuters.com, including major lawsuits, regulatory fines, and tax evasion allegations. It is recommended that a human conduct further due diligence into these matters.
```

## Prereqs

 - enable Custom Search API in your GCP project
 - create a Google API key
 - `cp media_check_agent/.env.example media_check_agent/.env`
 - put the API key into `media_check_agent/.env`

Note that if you are using Cloud Shell Editor, you need to click View -> Toggle Hidden Files to be able to see `.env` files.


## Sample scripts

```python
uv run python media_check_agent/internal_helper_functions.py
```

this script demonstrates how to run Google search queries programmatically, and how to analyze text for spesific adverse keywords.

## High-level instructions

 - Looking at the agent specification above and the provided code snippets, implement an ADK agent
 - Test the agent locally (`uv run adk run agent04_media_check_agent` or `uv run adk web`)
- Deploy the agent to Agent Engine
- Test the deployed version of the agent
- Link the agent to a Gemini Enterprise application
- Make sure it works in Gemini Enterprise as well
