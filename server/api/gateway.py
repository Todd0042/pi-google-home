"""
Pi Google Home — Streaming Gateway Server
FastAPI & WebSocket server coordinating real-time audio ingestion from the Pi,
GPU-accelerated STT (Whisper), LLM reasoning, and neural TTS synthesis (Piper).
"""

import os
import sys
import json
import time
import asyncio
import threading
import traceback
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Path setup
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from shared.constants import (
    DEFAULT_SERVER_PORT,
    DEFAULT_SERVER_HOST,
    AssistantState,
)
from shared.protocol import Message, EventType
from server.stt.transcriber import WhisperTranscriber
from server.tts.synthesizer import PiperSynthesizer
from server.brain.intent import IntentEngine
from server.integrations.weather import get_weather_display_data

load_dotenv()

app = FastAPI(title="Pi Google Home Server Gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active Display UI WebSocket connections
display_connections: set[WebSocket] = set()

async def broadcast_to_displays(event_type: str, payload: dict):
    """Broadcasts assistant and environmental events to all connected display dashboards."""
    if not display_connections:
        return
    msg = json.dumps({"type": event_type, "payload": payload})
    disconnected = set()
    for ws in list(display_connections):
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.add(ws)
    if disconnected:
        display_connections.difference_update(disconnected)

# Global Engine Singletons (Lazy-loaded on startup)
stt_engine: Optional[WhisperTranscriber] = None
tts_engine: Optional[PiperSynthesizer] = None
brain_engine: Optional[IntentEngine] = None

@app.on_event("startup")
async def startup_event():
    global stt_engine, tts_engine, brain_engine
    print("\n=======================================================")
    print(" Starting Pi Google Home Heavy-Lifting Server...")
    print("=======================================================")
    
    # 1. Initialize STT (faster-whisper on GPU)
    model_size = os.getenv("WHISPER_MODEL", "base.en")
    device = os.getenv("WHISPER_DEVICE", "cuda")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "float16")
    stt_engine = WhisperTranscriber(model_size=model_size, device=device, compute_type=compute_type)

    # 2. Initialize TTS (Piper)
    tts_engine = PiperSynthesizer()

    # 3. Initialize Brain (Intent & LLM)
    brain_engine = IntentEngine()
    print("=======================================================")
    print(" Server is READY and listening for Raspberry Pi clients")
    print("=======================================================\n")

@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "stt_device": stt_engine.device if stt_engine else "uninitialized",
        "tts_voice": tts_engine.voice_name if tts_engine else "uninitialized",
    }

@app.get("/api/weather")
async def weather_api(location: Optional[str] = None):
    """Fetches full display weather JSON with auto-location discovery."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_weather_display_data, location)

@app.websocket("/ws/display")
async def display_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    display_connections.add(websocket)
    client_ip = websocket.client.host if websocket.client else "unknown"
    print(f"[DISPLAY CONNECTED] Dashboard connected from {client_ip}")
    try:
        # Send initial ready state
        await websocket.send_text(json.dumps({"type": "state_change", "payload": {"state": "ready"}}))
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        print(f"[DISPLAY DISCONNECTED] Dashboard from {client_ip} disconnected.")
    except Exception as e:
        print(f"[DISPLAY WS ERROR] {e}")
    finally:
        display_connections.discard(websocket)

@app.websocket("/ws/assistant")
async def assistant_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_ip = websocket.client.host if websocket.client else "unknown"
    print(f"\n[CLIENT CONNECTED] Raspberry Pi connected from {client_ip}")

    # Audio buffer for the active speech turn
    audio_buffer = bytearray()
    current_state = AssistantState.IDLE

    try:
        while True:
            # Receive either binary audio frame or text JSON control event
            data = await websocket.receive()

            # Handle Binary Audio Stream (Raw PCM from Pi Microphone)
            if "bytes" in data and data["bytes"]:
                chunk = data["bytes"]
                audio_buffer.extend(chunk)

            # Handle Text Control Messages (JSON Protocol)
            elif "text" in data and data["text"]:
                msg = Message.from_json(data["text"])
                event_type = msg.type

                if event_type == EventType.WAKE_TRIGGERED:
                    print("\n[EVENT] Wake word detected by client! Opening capture stream...")
                    audio_buffer.clear()
                    current_state = AssistantState.LISTENING
                    await websocket.send_text(
                        Message(type=EventType.STATE_CHANGE, payload={"state": AssistantState.LISTENING}).to_json()
                    )
                    await broadcast_to_displays("state_change", {"state": "listening"})

                elif event_type == EventType.SPEECH_END:
                    print(f"[EVENT] Speech ended. Captured {len(audio_buffer)} audio bytes.")
                    current_state = AssistantState.THINKING
                    await websocket.send_text(
                        Message(type=EventType.STATE_CHANGE, payload={"state": AssistantState.THINKING}).to_json()
                    )
                    await broadcast_to_displays("state_change", {"state": "thinking"})

                    if len(audio_buffer) < 3200:  # Less than 100ms of audio
                        print("[WARN] Audio buffer too small. Ignoring.")
                        await websocket.send_text(
                            Message(type=EventType.STATE_CHANGE, payload={"state": AssistantState.IDLE}).to_json()
                        )
                        await broadcast_to_displays("state_change", {"state": "ready"})
                        continue

                    # 1. Transcribe audio (Whisper on GPU)
                    loop = asyncio.get_event_loop()
                    transcription = await loop.run_in_executor(
                        None, stt_engine.transcribe, bytes(audio_buffer)
                    )
                    await websocket.send_text(
                        Message(type=EventType.TRANSCRIPTION, payload={"text": transcription}).to_json()
                    )
                    await broadcast_to_displays("transcription", {"text": transcription})

                    if not transcription:
                        print("[WARN] No speech detected in audio buffer.")
                        await websocket.send_text(
                            Message(type=EventType.STATE_CHANGE, payload={"state": AssistantState.IDLE}).to_json()
                        )
                        await broadcast_to_displays("state_change", {"state": "ready"})
                        continue

                    # 2+3. Stream LLM reply sentences and overlap Piper TTS with
                    # Gemini generation: each completed sentence is synthesized as
                    # soon as it streams out and sent to the Pi immediately.
                    results: asyncio.Queue = asyncio.Queue()

                    def produce_reply():
                        try:
                            for item in brain_engine.process_stream(transcription):
                                if isinstance(item, dict) and "command" in item:
                                    loop.call_soon_threadsafe(
                                        results.put_nowait, ("command", item["command"], None)
                                    )
                                else:
                                    wav_bytes = tts_engine.synthesize(item)
                                    loop.call_soon_threadsafe(
                                        results.put_nowait, ("audio", item, wav_bytes)
                                    )
                        except Exception as exc:
                            print(f"[ERROR] Reply producer: {exc}")
                        finally:
                            loop.call_soon_threadsafe(results.put_nowait, ("done", None, None))

                    threading.Thread(target=produce_reply, daemon=True).start()

                    current_state = AssistantState.SPEAKING
                    await websocket.send_text(
                        Message(type=EventType.STATE_CHANGE, payload={"state": AssistantState.SPEAKING}).to_json()
                    )
                    await broadcast_to_displays("state_change", {"state": "speaking"})

                    while True:
                        kind, payload, extra = await results.get()
                        if kind == "done":
                            break
                        if kind == "command":
                            print(f"[COMMAND] Sending local action to Pi: {payload}")
                            await websocket.send_text(
                                Message(type=EventType.COMMAND, payload=payload).to_json()
                            )
                            await broadcast_to_displays("command", payload)
                            continue
                        sentence, wav_bytes = payload, extra
                        print(f"[REPLY] \"{sentence}\"")
                        await broadcast_to_displays("assistant_reply", {"text": sentence})
                        await websocket.send_text(
                            Message(type=EventType.TTS_START, payload={"size": len(wav_bytes), "format": "wav"}).to_json()
                        )
                        await websocket.send_bytes(wav_bytes)

                    await websocket.send_text(
                        Message(type=EventType.TTS_END).to_json()
                    )

                    # Return to IDLE
                    current_state = AssistantState.IDLE
                    await websocket.send_text(
                        Message(type=EventType.STATE_CHANGE, payload={"state": AssistantState.IDLE}).to_json()
                    )
                    await broadcast_to_displays("state_change", {"state": "ready"})
                    audio_buffer.clear()

    except WebSocketDisconnect:
        print(f"[CLIENT DISCONNECTED] Client {client_ip} closed connection.")
    except Exception as e:
        print(f"[ERROR] WebSocket error: {e}")
        traceback.print_exc()
        try:
            await websocket.send_text(Message(type=EventType.ERROR, payload={"error": str(e)}).to_json())
        except Exception:
            pass

# Mount static files for Smart Display UI
_display_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../display"))
if os.path.exists(_display_dir):
    app.mount("/display", StaticFiles(directory=_display_dir, html=True), name="display")

def run():
    import uvicorn
    host = os.getenv("SERVER_HOST", DEFAULT_SERVER_HOST)
    port = int(os.getenv("SERVER_PORT", DEFAULT_SERVER_PORT))
    uvicorn.run("server.api.gateway:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    run()
