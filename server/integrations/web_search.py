"""
Pi Google Home — Web Search & Research Skill
Live web research using DuckDuckGo (ddgs) and Wikipedia API (Zero API key required)
with keyword salience ranking and speech-optimized text cleaning.
"""

import re
import requests
from typing import Optional
from ddgs import DDGS

def clean_speech_text(text: str) -> str:
    """Removes Wikipedia phonetic guides, citations, URLs, and formatting for clean spoken TTS."""
    if not text:
        return ""
    # Remove parenthetical pronunciation guides like (/ˈkænbrə/ ⓘ KAN-brə; ...)
    text = re.sub(r'\s*\([^)]*(?:/|ⓘ|IPA|pronun|listen|alias)[^)]*\)', '', text)
    # Remove citations like [1], [28][8]
    text = re.sub(r'\[\d+(?:,\s*\d+)*\]', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Clean up multiple spaces and punctuation artifacts
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s+([,.?!])', r'\1', text)
    return text.strip()

def search_wikipedia(query: str) -> Optional[str]:
    """Queries the Wikipedia REST API for a concise factual summary."""
    try:
        clean_query = query.lower()
        for prefix in ["who is", "who was", "what is", "what was", "tell me about", "define", "explain"]:
            if clean_query.startswith(prefix):
                clean_query = clean_query[len(prefix):].strip()
        clean_query = clean_query.strip("?.").strip()

        if not clean_query:
            return None

        # 1. Direct title summary
        title = clean_query.title().replace(" ", "_")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}"
        res = requests.get(url, timeout=3, headers={"User-Agent": "PiGoogleHome/1.0"})

        if res.status_code == 200:
            data = res.json()
            if data.get("type") != "disambiguation":
                extract = data.get("extract", "")
                if extract and len(extract) > 30:
                    clean = clean_speech_text(extract)
                    sentences = re.split(r'(?<=[.!?])\s+', clean)
                    return " ".join(sentences[:2])

        # 2. Wikipedia search API fallback
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={requests.utils.quote(clean_query)}&format=json&utf8=1"
        s_res = requests.get(search_url, timeout=3, headers={"User-Agent": "PiGoogleHome/1.0"}).json()
        items = s_res.get("query", {}).get("search", [])
        if items:
            best_title = items[0]["title"]
            sum_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(best_title)}"
            sum_res = requests.get(sum_url, timeout=3, headers={"User-Agent": "PiGoogleHome/1.0"})
            if sum_res.status_code == 200:
                data = sum_res.json()
                if data.get("type") != "disambiguation":
                    extract = data.get("extract", "")
                    if extract and len(extract) > 30:
                        clean = clean_speech_text(extract)
                        sentences = re.split(r'(?<=[.!?])\s+', clean)
                        return " ".join(sentences[:2])
    except Exception:
        pass
    return None

def search_web(query: str, max_results: int = 5) -> str:
    """
    Performs real-time web search and returns a concise, speech-friendly answer
    using keyword salience scoring across search snippets.
    """
    # 1. Try Wikipedia first for biographical / definitional questions
    clean_q = query.lower().strip()
    is_definitional = any(clean_q.startswith(p) for p in ["who is", "who was", "what is", "what was", "tell me about", "define", "what are"])
    if is_definitional:
        wiki_answer = search_wikipedia(query)
        if wiki_answer:
            return wiki_answer

    # 2. DuckDuckGo web search with keyword salience scoring
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))
        stop_words = {
            "who", "what", "when", "where", "why", "how", "is", "was", "are", "were",
            "the", "in", "on", "at", "a", "an", "to", "for", "of", "and", "or", "it",
            "can", "you", "tell", "me", "about"
        }
        query_words = set(re.findall(r'[a-z0-9]+', query.lower())) - stop_words

        candidates = []
        for r in results:
            body = r.get("body", "")
            if not body:
                continue

            # Strip leading dates like 'Feb 11, 2024 · ' or '2 days ago - '
            body = re.sub(r'^(?:[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}\s*[-·•–]\s*)', '', body)
            body = re.sub(r'^(?:\d+\s+(?:days?|hours?|weeks?|months?|years?)\s+ago\s*[-·•–]\s*)', '', body)

            sentences = re.split(r'(?<=[.!?])\s+', body)
            for s in sentences:
                s_clean = clean_speech_text(s)
                if len(s_clean) < 25 or len(s_clean) > 280:
                    continue
                # Score based on keyword hits
                s_words = set(re.findall(r'[a-z0-9]+', s_clean.lower()))
                hits = len(query_words.intersection(s_words))
                if hits > 0:
                    candidates.append((hits, s_clean))

        if candidates:
            # Sort by keyword match count descending
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

    except Exception as e:
        print(f"[WARN] Web search failed: {e}")

    # Fallback to Wikipedia if DDG had no clear candidates
    wiki_answer = search_wikipedia(query)
    if wiki_answer:
        return wiki_answer

    return f"I searched for {query}, but could not find a definitive answer."

if __name__ == "__main__":
    print("Test Wiki:", search_web("who is Alan Turing?"))
    print("Test DDG:", search_web("who won the Super Bowl in 2024?"))
    print("Test Capital:", search_web("what is the capital of Australia?"))
    print("Test Science:", search_web("why is the sky blue?"))
