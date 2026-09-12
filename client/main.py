#!/usr/bin/env python3
"""
Pi Google Home — Client Voice Assistant Daemon
Coordinates wake word listening, audio capture, network streaming to host PC server,
and HDMI speaker voice response playback.
"""

import os
import sys
import time
import math
import asyncio
import argparse
import numpy as np
import pyaudio

# Add parent directory to path for local imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from client.audio.playback import AudioPlayer
from client.network.client_transport import AssistantClientTransport
import openwakeword
from openwakeword.model import Model

# Audio & Streaming Standards
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280  # 80ms chunks for wake word
STREAM_CHUNK = 1024
DEFAULT_SERVER_URL = "ws://192.168.1.236:8765/ws/assistant"
WAKE_KEYWORD = "hey_jarvis"
WAKE_THRESHOLD = 0.40
SPEECH_RMS = 120.0
POST_SPEECH_SILENCE_SEC = 1.2
MAX_RECORDING_SEC = 6.0

def calculate_rms(data: np.ndarray) -> float:
    if len(data) == 0:
        return 0.0
    return float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))

class AssistantClient:
    def __init__(self, server_url: str = DEFAULT_SERVER_URL, keyword: str = WAKE_KEYWORD):
        self.server_url = server_url
        self.keyword = keyword
        self.player = AudioPlayer()
        self.pa = pyaudio.PyAudio()
        self.ambient_rms = 70.0  # Rolling baseline of room noise floor

        # Ensure hardware AGC is disabled for high-fidelity wake-word neural inference
        os.system("amixer -c 0 sset 'Auto Gain Control' off >/dev/null 2>&1")

        print(f"\n[INIT] Initializing openWakeWord models for keyword: '{self.keyword}'...")
        all_paths = openwakeword.get_pretrained_model_paths("onnx")
        selected = [p for p in all_paths if self.keyword in os.path.basename(p)] or all_paths
        self.oww_model = Model(wakeword_models=selected, inference_framework="onnx")
        self.active_model = list(self.oww_model.models.keys())[0]

        print(f"==> Assistant Client Ready! Target Wake Word: '{self.active_model}'")
        print(f"==> Host Server: {self.server_url}")

    async def record_and_stream(self, transport: AssistantClientTransport, mic_stream, baseline_ambient: float) -> None:
        """Records voice command until end-of-speech silence is detected, streaming to server."""
        print("\n[LISTENING] >>> Listening for your voice query... <<<", flush=True)
        speech_started = False
        silence_start_time = None
        record_start_time = time.time()
        peak_rms = 0.0

        # Calibrate directly from the continuous room noise baseline captured BEFORE keyword
        ambient_rms = max(30.0, baseline_ambient)
        speech_threshold = max(180.0, ambient_rms * 1.8)
        silence_threshold = max(ambient_rms * 1.25, ambient_rms + 25.0)
        post_speech_silence_sec = 0.65  # 650ms snappy silence cutoff

        while True:
            raw = mic_stream.read(STREAM_CHUNK, exception_on_overflow=False)
            await transport.stream_audio_chunk(raw)

            data = np.frombuffer(raw, dtype=np.int16)
            rms = calculate_rms(data)

            # Volume meter in terminal
            bars = "#" * min(int(rms / 100), 30)
            print(f"\rRecording: [{bars:<30}] (RMS: {rms:5.1f} | Cutoff: {silence_threshold:5.1f})", end="", flush=True)

            now = time.time()
            if rms > speech_threshold:
                if not speech_started:
                    speech_started = True
                peak_rms = max(peak_rms, rms)
                silence_start_time = None
            elif speech_started:
                # Dynamic silence: dropped below ambient silence threshold or 25% of speech peak
                dynamic_cutoff = max(silence_threshold, peak_rms * 0.25)
                if rms <= dynamic_cutoff:
                    if silence_start_time is None:
                        silence_start_time = now
                    elif now - silence_start_time >= post_speech_silence_sec:
                        print(f"\n[VAD] End of speech detected ({post_speech_silence_sec}s silence).")
                        break
                else:
                    silence_start_time = None

            if now - record_start_time >= MAX_RECORDING_SEC:
                print("\n[TIMEOUT] Max recording duration reached.")
                break

            await asyncio.sleep(0.001)

        await transport.send_event("speech_end")

    def _flush_mic_buffer(self, mic_stream):
        """Drains any queued audio in the PyAudio buffer recorded during playback."""
        try:
            available = mic_stream.get_read_available()
            if available > 0:
                mic_stream.read(available, exception_on_overflow=False)
        except Exception:
            pass

    async def handle_turn(self, mic_stream, baseline_ambient: float):
        """Executes a full interactive assistant turn with progressive streaming playback."""
        # 1. Play activation chime on monitor speakers
        try:
            self.player.play_chime("wake.wav")
        except Exception as e:
            print(f"[WARN] Chime playback error: {e}")

        # Drain chime audio from mic buffer before recording user speech
        self._flush_mic_buffer(mic_stream)

        # 2. Connect to Host PC Server
        transport = AssistantClientTransport(self.server_url)
        try:
            await transport.connect()
            await transport.send_event("wake_triggered")

            # 3. Stream user query with pre-calibrated ambient floor
            await self.record_and_stream(transport, mic_stream, baseline_ambient=baseline_ambient)

            # 4. Await response from server & stream audio playback progressively in RAM
            print("[THINKING] Waiting for server transcription & response...")

            def on_transcription(text: str):
                print(f"\n[YOU SAID]: \"{text}\"")

            def on_reply(text: str):
                print(f"[ASSISTANT]: \"{text}\"")

            def on_audio_chunk(audio_bytes: bytes):
                print(f"[SPEAKING] Streaming voice playback ({len(audio_bytes)} bytes) in memory...")
                self.player.play_wav_bytes(audio_bytes)

            await transport.receive_response(
                on_transcription=on_transcription,
                on_reply=on_reply,
                on_audio_chunk=on_audio_chunk,
            )

        except Exception as e:
            print(f"\n[ERROR] Communication error with server {self.server_url}: {e}")
            try:
                self.player.play_chime("cancel.wav")
            except Exception:
                pass
        finally:
            await transport.close()
            # Post-turn cleanup: Drain speaker echo from mic buffer and reset neural net history
            await asyncio.sleep(0.5)
            self._flush_mic_buffer(mic_stream)
            self.oww_model.reset()

    async def run(self):
        mic_stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )

        print("=" * 65)
        print(" Pi Google Home — Standalone Assistant Online")
        print(f" Say 'Hey Jarvis' to speak!")
        print(" Press Ctrl+C to quit.")
        print("=" * 65)

        try:
            while True:
                # Read 80ms chunk for wake word
                audio_raw = mic_stream.read(CHUNK_SIZE, exception_on_overflow=False)
                audio_data = np.frombuffer(audio_raw, dtype=np.int16)
                rms = calculate_rms(audio_data)

                # Continuously track ambient noise floor while idle (exclude loud spikes)
                if rms < 300.0:
                    self.ambient_rms = 0.95 * self.ambient_rms + 0.05 * rms

                # Continuously feed audio into neural model to maintain temporal embedding context
                predictions = self.oww_model.predict(audio_data)
                score = predictions.get(self.active_model, 0.0)

                # Diagnostic log whenever audio resembles wake word features
                if score >= 0.15:
                    print(f"\n[VOICE ACTIVITY] Wake word '{self.active_model}' score: {score:.3f} | RMS: {rms:.1f}", flush=True)

                if score >= WAKE_THRESHOLD:
                    print(f"\n\n{'*' * 60}")
                    print(f" [WAKE TRIGGERED] Score: {score:.3f} | Ambient: {self.ambient_rms:.1f} RMS", flush=True)
                    print(f"{'*' * 60}", flush=True)
                    await self.handle_turn(mic_stream, baseline_ambient=self.ambient_rms)
                    self._flush_mic_buffer(mic_stream)
                    self.oww_model.reset()
                    print("\n[READY] Listening for 'Hey Jarvis' again...\n", flush=True)

                await asyncio.sleep(0.002)

        except KeyboardInterrupt:
            print("\nShutting down assistant client...")
        finally:
            mic_stream.stop_stream()
            mic_stream.close()
            self.pa.terminate()
            self.player.close()

def main():
    parser = argparse.ArgumentParser(description="Pi Google Home Voice Client")
    parser.add_argument("--server", type=str, default=DEFAULT_SERVER_URL, help="Host PC WebSocket Server URL")
    parser.add_argument("--keyword", type=str, default=WAKE_KEYWORD, help="Wake word keyword")
    args = parser.parse_args()

    client = AssistantClient(server_url=args.server, keyword=args.keyword)
    asyncio.run(client.run())

if __name__ == "__main__":
    main()
