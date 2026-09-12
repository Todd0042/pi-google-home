"""
Pi Google Home — Web Search & Research Skill
Live web research using DuckDuckGo (ddgs) and Wikipedia API (Zero API key required).
"""

import re
import requests
from typing import Optional
from ddgs import DDGS

def search_wikipedia(query: str) -> Optional[str]:
    """Queries the Wikipedia REST API for a concise factual summary."""
    try:
        clean_query = query.lower()
        for prefix in ["who is", "who was", "what is", "what was", "tell me about", "define"]:
            clean_query = clean_query.replace(prefix, "").strip()
        clean_query = clean_query.strip("?.").strip()

        if not clean_query:
            return None

        # Format title
        title = clean_query.title().replace(" ", "_")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}"
        res = requests.get(url, timeout=4, headers={"User-Agent": "PiGoogleHome/1.0"})

        if res.status_code == 200:
            data = res.json()
            extract = data.get("extract", "")
            if extract and len(extract) > 40:
                # Take first 1-2 sentences
                sentences = re.split(r'(?<=[.!?])\s+', extract)
                return " ".join(sentences[:2])
    except Exception:
        pass
    return None

def search_web(query: str, max_results: int = 2) -> str:
    """
    Performs real-time web search and returns a concise, speech-friendly answer.
    """
    # 1. Try Wikipedia first for clean biographical / definition queries
    wiki_answer = search_wikipedia(query)
    if wiki_answer:
        return wiki_answer

    # 2. DuckDuckGo web search
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))
        if results:
            snippets = []
            for r in results:
                body = r.get("body", "").strip()
                if body:
                    snippets.append(body)

            if snippets:
                combined = " ".join(snippets)
                # Clean up multiple spaces, brackets, ellipses
                combined = re.sub(r'\[.*?\]', '', combined)
                combined = re.sub(r'\s+', ' ', combined).strip()
                sentences = re.split(r'(?<=[.!?])\s+', combined)
                return " ".join(sentences[:2])

    except Exception as e:
        print(f"[WARN] Web search failed: {e}")

    return f"I searched the web for {query}, but couldn't find a direct answer."

if __name__ == "__main__":
    print("Test Wiki:", search_web("who is Alan Turing?"))
    print("Test DDG:", search_web("who won the Super Bowl in 2024?"))
    print("Test Science:", search_web("why is the ocean salty?"))
