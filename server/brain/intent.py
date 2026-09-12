"""
Pi Google Home — Intent & Reasoning Engine
Evaluates user queries, executes local skills (weather, timers, time),
or performs real-time web research and LLM reasoning.
"""

import os
import re
import datetime
from typing import Optional
from server.integrations.weather import get_weather
from server.integrations.web_search import search_web

class IntentEngine:
    def __init__(self, gemini_api_key: Optional[str] = None):
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self._gemini_client = None

        if self.gemini_api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.gemini_api_key)
                print("==> Gemini Reasoning Engine connected with Google Search Grounding.")
            except Exception as e:
                print(f"[WARN] Failed to initialize Gemini client: {e}")
        else:
            print("==> Running Built-in Autonomous Web Research Engine (Zero API keys required).")

    def process(self, query: str) -> str:
        """
        Processes a transcribed voice query and returns a conversational response string.
        """
        clean = query.strip().lower()
        if not clean:
            return "I'm listening, how can I help?"

        # 1. Fast Local Time & Date Intents
        if any(w in clean for w in ["what time", "current time", "time is it"]):
            now = datetime.datetime.now().strftime("%I:%M %p")
            return f"It is currently {now}."

        if any(w in clean for w in ["what day", "what date", "today's date"]):
            today = datetime.datetime.now().strftime("%A, %B %d, %Y")
            return f"Today is {today}."

        if "who are you" in clean or "what is your name" in clean:
            return "I am your Raspberry Pi smart assistant, running Arch Linux ARM."

        # 2. Weather Intent (Open-Meteo)
        if any(w in clean for w in ["weather", "temperature", "forecast", "how hot", "how cold", "rain"]):
            city = None
            m = re.search(r'(?:in|for)\s+([a-zA-Z\s]+)', clean)
            if m:
                city = m.group(1).replace("today", "").replace("tomorrow", "").strip()
            return get_weather(city)

        # 3. Gemini LLM with Google Search Grounding (if API key provided)
        if self._gemini_client:
            try:
                system_prompt = (
                    "You are a helpful, voice-first smart display assistant. "
                    "Provide accurate, clear, and direct answers in 1 to 2 concise sentences suitable for spoken audio. "
                    "Do not use markdown, bullet points, asterisks, or citations in your speech output."
                )
                response = self._gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=clean,
                    config={
                        "system_instruction": system_prompt,
                        # Enable Google Search grounding for real-time web research
                        "tools": [{"google_search": {}}],
                    },
                )
                text = response.text.strip()
                # Clean up any lingering markdown asterisks
                text = re.sub(r'[*_#`]', '', text)
                return text
            except Exception as e:
                print(f"[WARN] Gemini reasoning failed ({e}), falling back to web search...")

        # 4. Built-in Web Search & Research (Zero API Keys)
        print(f"[RESEARCH] Querying web search for: '{query}'...")
        web_answer = search_web(query)
        if web_answer and len(web_answer) > 10:
            return web_answer

        return f"I couldn't find a definitive answer for {query}."

if __name__ == "__main__":
    engine = IntentEngine()
    print("\n--- Test Weather ---")
    print(engine.process("what's the weather in Seattle?"))
    print("\n--- Test Web Research ---")
    print(engine.process("who is Albert Einstein?"))
    print("\n--- Test Real-Time Event ---")
    print(engine.process("who won the Super Bowl in 2024?"))
