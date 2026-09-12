#!/usr/bin/env python3
"""
End-to-End WebSocket Gateway Test
Connects to ws://127.0.0.1:8765/ws/assistant, simulates a client session,
sends audio, and receives transcription, reply, and TTS voice audio.
"""

import asyncio
import json
import numpy as np
import websockets

SERVER_URL = "ws://127.0.0.1:8765/ws/assistant"

async def test_session():
    print(f"==> Connecting to {SERVER_URL}...")
    async with websockets.connect(SERVER_URL) as ws:
        print("Connected!")

        # 1. Send wake event
        print("\n[1/4] Sending wake_triggered...")
        await ws.send(json.dumps({"type": "wake_triggered"}))
        state_msg = await ws.recv()
        print("Received:", state_msg)

        # 2. Simulate streaming 1 second of audio (e.g. 16kHz silence / tone)
        print("\n[2/4] Streaming 1.5 seconds of simulated PCM audio...")
        chunk = np.zeros(1024, dtype=np.int16).tobytes()
        for _ in range(int(16000 * 1.5 / 1024)):
            await ws.send(chunk)
            await asyncio.sleep(0.02)

        # 3. Send speech end
        print("\n[3/4] Sending speech_end...")
        await ws.send(json.dumps({"type": "speech_end"}))

        # 4. Wait for responses
        print("\n[4/4] Awaiting server responses...")
        tts_audio_received = 0

        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                if isinstance(msg, bytes):
                    tts_audio_received += len(msg)
                    print(f" -> Received binary TTS audio chunk: {len(msg)} bytes")
                else:
                    data = json.loads(msg)
                    mtype = data.get("type")
                    payload = data.get("payload", {})
                    print(f" -> Received event: {mtype} | Payload: {payload}")
                    if mtype == "state_change" and payload.get("state") == "IDLE":
                        print("\n[SUCCESS] Server completed full turn and returned to IDLE!")
                        break
            except asyncio.TimeoutError:
                print("[TIMEOUT] No more messages received.")
                break

        print(f"\nTotal TTS Audio Bytes Received: {tts_audio_received}")

if __name__ == "__main__":
    asyncio.run(test_session())
