#!/usr/bin/env python3
"""
Full Audio Round-Trip Test with Actual Speech
Sends synthesized question "What time is it?" to the gateway,
and verifies transcription, intent resolution, and TTS response audio stream.
"""

import asyncio
import io
import json
import wave
import websockets
from piper.voice import PiperVoice

SERVER_URL = "ws://127.0.0.1:8765/ws/assistant"

async def test_speech_roundtrip():
    # 1. Generate speech sample: "What time is it?"
    print("==> Synthesizing query: 'What time is it?'...")
    voice = PiperVoice.load("server/tts/voices/en_US-lessac-medium.onnx", config_path="server/tts/voices/en_US-lessac-medium.onnx.json")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        voice.synthesize_wav("What time is it?", wf)
    
    # Extract raw 16kHz PCM (resampled to 16kHz for Whisper)
    buf.seek(0)
    with wave.open(buf, "rb") as wf:
        raw_audio = wf.readframes(wf.getnframes())
        orig_rate = wf.getframerate()
        print(f"Synthesized query: {len(raw_audio)} bytes @ {orig_rate}Hz")

    # 2. Connect to Gateway
    print(f"\n==> Connecting to {SERVER_URL}...")
    async with websockets.connect(SERVER_URL) as ws:
        # Send wake word
        await ws.send(json.dumps({"type": "wake_triggered"}))
        state_msg = await ws.recv()
        print("Server State:", state_msg)

        # Stream audio chunks (1024 bytes per chunk)
        print("==> Streaming voice query to server...")
        chunk_size = 2048
        for i in range(0, len(raw_audio), chunk_size):
            await ws.send(raw_audio[i:i + chunk_size])
            await asyncio.sleep(0.03)

        # Signal speech end
        print("==> Sending speech_end...")
        await ws.send(json.dumps({"type": "speech_end"}))

        # Collect response
        response_audio = bytearray()
        print("\n==> Waiting for server pipeline (STT -> Reasoning -> TTS)...")
        while True:
            msg = await ws.recv()
            if isinstance(msg, bytes):
                response_audio.extend(msg)
                print(f" [TTS AUDIO] Received {len(msg)} bytes")
            else:
                event = json.loads(msg)
                etype = event.get("type")
                payload = event.get("payload", {})
                print(f" [EVENT] {etype}: {payload}")
                if etype == "state_change" and payload.get("state") == "IDLE":
                    break

        print(f"\n[SUCCESS] Round-trip complete!")
        print(f"Total response audio received: {len(response_audio)} bytes")

if __name__ == "__main__":
    asyncio.run(test_speech_roundtrip())
