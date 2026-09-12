"""
Pi Google Home — Intent & Reasoning Engine
Evaluates user queries, executes local intents (timers, weather, time),
or queries an LLM (Gemini API / Ollama) for general conversational reasoning.
"""

import os
import datetime
from typing import Optional

class IntentEngine:
    def __init__(self, llm_provider: str = "auto", gemini_api_key: Optional[str] = None):
        self.llm_provider = llm_provider
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self._gemini_client = None

        if self.gemini_api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.gemini_api_key)
                print("==> Gemini LLM Reasoning Engine connected.")
            except Exception as e:
                print(f"[WARN] Failed to initialize Gemini client: {e}")

    def process(self, query: str) -> str:
        """
        Processes a transcribed voice query and returns a conversational response string.
        """
        clean = query.strip().lower()
        if not clean:
            return "I'm listening, how can I help?"

        # 1. Fast Local Intent Matching (Zero Latency)
        if any(w in clean for w in ["what time", "current time", "time is it"]):
            now = datetime.datetime.now().strftime("%I:%M %p")
            return f"It is currently {now}."

        if any(w in clean for w in ["what day", "what date", "today's date"]):
            today = datetime.datetime.now().strftime("%A, %B %d, %Y")
            return f"Today is {today}."

        if "who are you" in clean or "what is your name" in clean:
            return "I am your Raspberry Pi smart assistant, running Arch Linux ARM."

        # 2. LLM Reasoning (Gemini API)
        if self._gemini_client:
            try:
                system_prompt = (
                    "You are a friendly, concise voice assistant running on a Raspberry Pi smart display. "
                    "Keep answers brief, conversational, and direct (1 to 2 sentences max) suitable for speech."
                )
                response = self._gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=clean,
                    config={"system_instruction": system_prompt},
                )
                return response.text.strip()
            except Exception as e:
                print(f"[ERROR] LLM Generation error: {e}")

        # 3. Fallback Response
        return f"You said: {query}. I heard you loud and clear."

if __name__ == "__main__":
    engine = IntentEngine()
    print("Test Time:", engine.process("what time is it?"))
    print("Test Date:", engine.process("what date is today?"))
    print("Test Name:", engine.process("who are you?"))
