"""
Pi Google Home — Intent & Reasoning Engine
Evaluates user queries, executes local skills (weather, timers, time),
or performs real-time web research and LLM reasoning.
"""

import os
import re
import datetime
from typing import Optional
from dotenv import load_dotenv
from server.integrations.weather import get_weather, get_weather_context
from server.integrations.web_search import search_web, clean_speech_text

load_dotenv()

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

        # 2. Weather Intent (Powered by Gemini with Live Multi-Day Open-Meteo Forecast)
        weather_keywords = [
            "weather", "temperature", "forecast", "how hot", "how cold", "rain",
            "umbrella", "jacket", "windy", "sunny", "out there", "outside", "how's it look"
        ]
        if any(w in clean for w in weather_keywords):
            city = None
            m = re.search(r'(?:in|for)\s+([a-zA-Z\s]+)', clean)
            if m:
                city = m.group(1).replace("today", "").replace("tomorrow", "").strip()

            if self._gemini_client:
                weather_ctx = get_weather_context(city)
                weather_prompt = (
                    f"User Question: {query}\n\n"
                    f"Live Multi-Day Weather Data:\n{weather_ctx}\n\n"
                    "Using the live weather data above, answer the user's specific question (e.g. for today, tomorrow, or a specific day) "
                    "directly in 1 concise spoken sentence without markdown, asterisks, or disclaimers."
                )
                try:
                    response = self._gemini_client.models.generate_content(
                        model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
                        contents=weather_prompt,
                        config={
                            "system_instruction": "You are a fast, voice-first smart home assistant in Jacksonville, Florida. Answer directly in 1 short spoken sentence based on the provided live weather data. No markdown, asterisks, or disclaimers."
                        },
                    )
                    text = response.text.strip()
                    return clean_speech_text(text)
                except Exception as e:
                    print(f"[WARN] Gemini weather reasoning failed ({e}), falling back to local weather...")

            # Fallback to local deterministic weather if Gemini is unavailable
            return get_weather(city, query=clean)

        # 3. Gemini LLM Reasoning (Super-fast conversational intelligence)
        if self._gemini_client:
            try:
                system_prompt = (
                    "You are a fast, voice-first smart home assistant. The user is located in Jacksonville, Florida. "
                    "Be extremely direct, simple, and concise. "
                    "Provide a simple, clear 1-sentence answer for general questions or facts. "
                    "Do not give unsolicited background, lengthy safety disclaimers, or multi-paragraph context unless the user specifically asks you to 'explain', 'elaborate', or 'give details'. "
                    "Never use markdown, bullet points, asterisks, or citations."
                )
                model_to_use = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

                # If query needs external web search or latest info
                context = ""
                if any(w in clean for w in ["search for", "latest news", "today's news", "live score"]):
                    search_res = search_web(query)
                    if search_res:
                        context = f"\nRelevant web search data: {search_res}"

                prompt = f"{clean}{context}"
                try:
                    response = self._gemini_client.models.generate_content(
                        model=model_to_use,
                        contents=prompt,
                        config={"system_instruction": system_prompt},
                    )
                except Exception:
                    response = self._gemini_client.models.generate_content(
                        model="gemini-flash-latest",
                        contents=prompt,
                        config={"system_instruction": system_prompt},
                    )
                text = response.text.strip()
                return clean_speech_text(text)
            except Exception as e:
                print(f"[WARN] Gemini reasoning failed ({e}), falling back to web search...")

        # 4. Built-in Web Search & Research (Zero API Keys)
        print(f"[RESEARCH] Querying web search for: '{query}'...")
        web_answer = search_web(query)
        if web_answer and len(web_answer) > 10:
            return clean_speech_text(web_answer)

        return f"I couldn't find a definitive answer for {query}."

if __name__ == "__main__":
    engine = IntentEngine()
    print("\n--- Test Weather ---")
    print(engine.process("what's the weather in Seattle?"))
    print("\n--- Test Web Research ---")
    print(engine.process("who is Albert Einstein?"))
    print("\n--- Test Real-Time Event ---")
    print(engine.process("who won the Super Bowl in 2024?"))
