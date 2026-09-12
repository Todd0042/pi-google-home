"""
Pi Google Home — Intent & Reasoning Engine
Evaluates user queries, executes local skills (weather, timers, time),
or performs real-time web research and LLM reasoning.
"""

import os
import re
import time
import json
import datetime
from pathlib import Path
from typing import Iterator, Optional, Union, Dict
from dotenv import load_dotenv
from server.integrations.weather import get_weather, get_weather_context
from server.integrations.web_search import search_web, clean_speech_text

# Streaming reply tuning: cap generation so the model stops right after the
# one-sentence spoken answer instead of producing extra padding.
MAX_OUTPUT_TOKENS = 128
TEMPERATURE = 0.2
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")

# Persisted marker of the date Gemini hit its daily quota. Written once, checked
# on every query, cleared automatically the next calendar day.
QUOTA_BLOCK_FILE = Path(__file__).parent / ".gemini_quota_block"

def _int_to_words(n: int) -> str:
    """Converts 0-100 into spoken words (e.g. 37 -> 'thirty-seven') for crisp TTS."""
    ones = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
            "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
            "seventeen", "eighteen", "nineteen"]
    tens = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    if n < 20:
        return ones[n]
    if n == 100:
        return "one hundred"
    t, u = divmod(n, 10)
    return tens[t - 2] if u == 0 else f"{tens[t - 2]}-{ones[u]}"

load_dotenv()

class IntentEngine:
    def __init__(self, gemini_api_key: Optional[str] = None):
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self._gemini_client = None
        self._quota_blocked_today = False

        if self.gemini_api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.gemini_api_key)
                print("==> Gemini Reasoning Engine connected with Google Search Grounding.")
                self._load_quota_state()
            except Exception as e:
                print(f"[WARN] Failed to initialize Gemini client: {e}")
        else:
            print("==> Running Built-in Autonomous Web Research Engine (Zero API keys required).")

    def process(self, query: str) -> str:
        """
        Processes a transcribed voice query and returns a conversational response string.
        """
        parts = [p for p in self.process_stream(query) if isinstance(p, str)]
        return " ".join(parts)

    def process_stream(self, query: str) -> Iterator[Union[str, Dict]]:
        """
        Processes a query and yields reply sentences progressively as they become
        available. For LLM answers this streams from Gemini so TTS can begin on
        sentence one while the model finishes the rest of the reply.

        Local device commands yield a dict `{"command": ...}` (executed on the Pi)
        followed by a spoken confirmation sentence.
        """
        clean = query.strip().lower()
        if not clean:
            yield "I'm listening, how can I help?"
            return

        # 1. System Command Intents (executed locally on the Pi)
        command_match = self._match_system_command(clean)
        if command_match:
            command_dict, confirmation = command_match
            yield {"command": command_dict}
            yield confirmation
            return

        # 2. Fast Local Time & Date Intents
        if any(w in clean for w in ["what time", "current time", "time is it"]):
            now = datetime.datetime.now().strftime("%I:%M %p")
            yield f"It is currently {now}."
            return

        if any(w in clean for w in ["what day", "what date", "today's date"]):
            today = datetime.datetime.now().strftime("%A, %B %d, %Y")
            yield f"Today is {today}."
            return

        if "who are you" in clean or "what is your name" in clean:
            yield "I am your Raspberry Pi smart assistant, running Arch Linux ARM."
            return

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

            if self._gemini_available():
                try:
                    weather_ctx = get_weather_context(city)
                    weather_prompt = (
                        f"User Question: {query}\n\n"
                        f"Live Multi-Day Weather Data:\n{weather_ctx}\n\n"
                        "Using the live weather data above, answer the user's specific question (e.g. for today, tomorrow, or a specific day) "
                        "directly in 1 concise spoken sentence without markdown, asterisks, or disclaimers."
                    )
                    system_instruction = (
                        "You are a fast, voice-first smart home assistant in Jacksonville, Florida. "
                        "Answer directly in 1 short spoken sentence based on the provided live weather data. "
                        "No markdown, asterisks, or disclaimers."
                    )
                    text = clean_speech_text(self._stream_gemini(
                        contents=weather_prompt,
                        system_instruction=system_instruction,
                    ))
                    yield from self._yield_sentences(text)
                    return
                except Exception as e:
                    print(f"[WARN] Gemini weather reasoning failed ({e}), falling back to local weather...")

            # Fallback to local deterministic weather if Gemini is unavailable
            yield get_weather(city, query=clean)
            return

        # 3. Gemini LLM Reasoning (Super-fast conversational intelligence)
        if self._gemini_available():
            try:
                system_prompt = (
                    "You are a fast, voice-first smart home assistant. The user is located in Jacksonville, Florida. "
                    "Be extremely direct, simple, and concise. "
                    "Provide a simple, clear 1-sentence answer for general questions or facts. "
                    "Do not give unsolicited background, lengthy safety disclaimers, or multi-paragraph context unless the user specifically asks you to 'explain', 'elaborate', or 'give details'. "
                    "Never use markdown, bullet points, asterisks, or citations."
                )

                # If query needs external web search or latest info
                context = ""
                if any(w in clean for w in ["search for", "latest news", "today's news", "live score"]):
                    search_res = search_web(query)
                    if search_res:
                        context = f"\nRelevant web search data: {search_res}"

                prompt = f"{clean}{context}"
                text = clean_speech_text(self._stream_gemini(
                    contents=prompt,
                    system_instruction=system_prompt,
                ))
                yield from self._yield_sentences(text)
                return
            except Exception as e:
                print(f"[WARN] Gemini reasoning failed ({e}), falling back to web search...")

        # 4. Built-in Web Search & Research (Zero API Keys)
        print(f"[RESEARCH] Querying web search for: '{query}'...")
        web_answer = search_web(query)
        if web_answer and len(web_answer) > 10:
            yield clean_speech_text(web_answer)
            return

        yield f"I couldn't find a definitive answer for {query}."

    def _load_quota_state(self):
        """Loads yesterday/today quota-block marker from disk, clearing stale entries."""
        try:
            if QUOTA_BLOCK_FILE.exists():
                raw = QUOTA_BLOCK_FILE.read_text().strip()
                if raw == datetime.date.today().isoformat():
                    self._quota_blocked_today = True
                    print("[QUOTA] Gemini daily quota exhausted; using local fallbacks until tomorrow.")
                else:
                    QUOTA_BLOCK_FILE.unlink()
        except Exception:
            pass

    def _gemini_available(self) -> bool:
        """True only if the Gemini client exists and today's quota is not already known-exhausted."""
        if not self._gemini_client or self._quota_blocked_today:
            return False
        return True

    def _block_quota(self):
        """Remembers that today's Gemini quota is exhausted so no API calls are attempted again today."""
        self._quota_blocked_today = True
        try:
            QUOTA_BLOCK_FILE.write_text(datetime.date.today().isoformat())
        except Exception:
            pass
        print("[QUOTA] Gemini daily quota hit. Blocking LLM calls until tomorrow.")

    def _match_system_command(self, clean: str):
        """Detects local Pi device commands. Returns (command_dict, spoken_confirmation) or None."""
        # Set volume to a specific percentage ("set volume to 50", "volume at 75 percent", "volume 30")
        m = re.search(r"set (?:the )?volume to (\d{1,3})", clean)
        if not m:
            m = re.search(r"volume (?:to|at) (\d{1,3})", clean)
        if not m:
            m = re.search(r"volume\s+(\d{1,3})\s*$", clean)
        if m:
            value = max(0, min(100, int(m.group(1))))
            return ({"action": "volume_set", "value": value},
                    f"Volume set to {_int_to_words(value)} percent.")

        # Volume up / down by 5%
        if re.search(r"volume up|turn (?:the )?volume up|increase (?:the )?volume|\blouder\b", clean):
            return ({"action": "volume_delta", "value": 5}, "Volume up five percent.")
        if re.search(r"volume down|turn (?:the )?volume down|decrease (?:the )?volume|lower (?:the )?volume|\bquieter\b", clean):
            return ({"action": "volume_delta", "value": -5}, "Volume down five percent.")

        # Reboot the Pi ("reboot" / "re-boot" / "restart")
        if re.search(r"\bre[\s-]*boot\b|\brestart\b", clean):
            return ({"action": "reboot"}, "Rebooting the Raspberry Pi now.")

        # Shut down / power off the Pi safely ("shutdown" / "shut down" / "power off")
        if re.search(r"\bshut[\s-]*down\b|\bpower[\s-]*(?:off|down)\b|" \
                     r"\bturn off (?:the )?(?:pi|pie|raspberry(?:\s*pi)?|device)\b", clean):
            return ({"action": "shutdown"}, "Powering off the Raspberry Pi now.")

        # Display off / on
        if re.search(r"display off|screen off|turn off (?:the )?(?:display|screen)", clean):
            return ({"action": "display_off"}, "Turning the display off.")
        if re.search(r"turn (?:the )?(?:display|screen) on|display on|screen on", clean):
            return ({"action": "display_on"}, "Turning the display on.")

        return None

    def _stream_gemini(self, contents: str, system_instruction: str) -> str:
        """Streams a Gemini completion, falling back to a non-streaming call on error."""
        config = {
            "system_instruction": system_instruction,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "temperature": TEMPERATURE,
        }
        model_to_use = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        try:
            return self._consume_stream(
                self._gemini_client.models.generate_content_stream(
                    model=model_to_use,
                    contents=contents,
                    config=config,
                )
            )
        except Exception as e:
            # Quota / rate-limit (429): remember it for the rest of the day and
            # bail to the local fallback instead of burning another call.
            try:
                from google.genai import errors as genai_errors
                if isinstance(e, genai_errors.APIError) and getattr(e, "code", None) == 429:
                    self._block_quota()
                    raise
            except Exception:
                pass
            print(f"[WARN] Gemini streaming failed ({e}), retrying non-streaming...")
            return self._gemini_client.models.generate_content(
                model=model_to_use,
                contents=contents,
                config=config,
            ).text.strip()

    def _consume_stream(self, stream) -> str:
        """Accumulates text from a streamed Gemini response."""
        t0 = time.perf_counter()
        parts = []
        for chunk in stream:
            if chunk.text:
                parts.append(chunk.text)
        text = "".join(parts).strip()
        dt = (time.perf_counter() - t0) * 1000.0
        print(f"[LLM] Gemini streamed reply in {dt:.0f}ms ({len(text)} chars)")
        return text

    def _yield_sentences(self, text: str) -> Iterator[str]:
        """Yields complete sentences from text, draining any trailing partial."""
        if not text:
            yield "I couldn't find a definitive answer for that."
            return
        remainder = text
        while True:
            parts = _SENTENCE_BOUNDARY.split(remainder, maxsplit=1)
            if len(parts) == 2:
                yield parts[0].strip()
                remainder = parts[1]
            else:
                tail = remainder.strip()
                if tail:
                    yield tail
                return

if __name__ == "__main__":
    engine = IntentEngine()
    print("\n--- Test Weather ---")
    print(engine.process("what's the weather in Seattle?"))
    print("\n--- Test Web Research ---")
    print(engine.process("who is Albert Einstein?"))
    print("\n--- Test Real-Time Event ---")
    print(engine.process("who won the Super Bowl in 2024?"))
