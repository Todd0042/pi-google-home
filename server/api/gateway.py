"""
Pi Google Home — Streaming Gateway Server
FastAPI & WebSocket server coordinating real-time audio ingestion from the Pi,
GPU-accelerated STT (Whisper), LLM reasoning, and neural TTS synthesis (Piper).
"""

import os
import sys
import json
import asyncio
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
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

load_dotenv()

app = FastAPI(title="Pi Google Home Server Gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

                elif event_type == EventType.SPEECH_END:
                    print(f"[EVENT] Speech ended. Captured {len(audio_buffer)} audio bytes.")
                    current_state = AssistantState.THINKING
                    await websocket.send_text(
                        Message(type=EventType.STATE_CHANGE, payload={"state": AssistantState.THINKING}).to_json()
                    )

                    if len(audio_buffer) < 3200:  # Less than 100ms of audio
                        print("[WARN] Audio buffer too small. Ignoring.")
                        await websocket.send_text(
                            Message(type=EventType.STATE_CHANGE, payload={"state": AssistantState.IDLE}).to_json()
                        )
                        continue

                    # 1. Transcribe audio (Whisper on GPU)
                    loop = asyncio.get_event_loop()
                    transcription = await loop.run_in_executor(
                        None, stt_engine.transcribe, bytes(audio_buffer)
                    )
                    await websocket.send_text(
                        Message(type=EventType.TRANSCRIPTION, payload={"text": transcription}).to_json()
                    )

                    if not transcription:
                        print("[WARN] No speech detected in audio buffer.")
                        await websocket.send_text(
                            Message(type=EventType.STATE_CHANGE, payload={"state": AssistantState.IDLE}).to_json()
                        )
                        continue

                    # 2. Reasoning / Intent resolution (Local intents or LLM)
                    reply_text = await loop.run_in_executor(
                        None, brain_engine.process, transcription
                    )
                    print(f"[REPLY] \"{reply_text}\"")
                    await websocket.send_text(
                        Message(type=EventType.ASSISTANT_REPLY, payload={"text": reply_text}).to_json()
                    )

                    # 3. Neural Voice Synthesis (Piper)
                    current_state = AssistantState.SPEAKING
                    await websocket.send_text(
                        Message(type=EventType.STATE_CHANGE, payload={"state": AssistantState.SPEAKING}).to_json()
                    )
                    
                    wav_bytes = await loop.run_in_executor(
                        None, tts_engine.synthesize, reply_text
                    )

                    # Notify client audio is starting, send audio, then notify end
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
                    audio_buffer.clear()

    except WebSocketDisconnect:
        print(f"[CLIENT DISCONNECTED] Client {client_ip} closed connection.")
    except Exception as e:
        print(f"[ERROR] WebSocket error: {e}")
        try:
            await websocket.send_text(Message(type=EventType.ERROR, payload={"error": str(e)}).to_json())
        except Exception:
            pass

def run():
    import uvicorn
    host = os.getenv("SERVER_HOST", DEFAULT_SERVER_HOST)
    port = int(os.getenv("SERVER_PORT", DEFAULT_SERVER_PORT))
    uvicorn.run("server.api.gateway:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    run()
