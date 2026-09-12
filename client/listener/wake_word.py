#!/usr/bin/env python3
"""
Pi Google Home — Local Wake Word Listener
Continuously listens on the USB Microphone using openWakeWord (ONNX Runtime).
Plays an acknowledgment chime via the 15" HDMI monitor speakers when triggered.
Optimized for Raspberry Pi 3 B+ Cortex-A53 quad-core CPU.
"""

import os
import sys
import time
import math
import struct
import argparse
import numpy as np
import pyaudio
import openwakeword
from openwakeword.model import Model

# Add parent directory to path for local imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from audio.playback import AudioPlayer

# Standard audio parameters for openWakeWord
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280  # 80ms chunks (1280 samples @ 16kHz)
DEFAULT_THRESHOLD = 0.5
COOLDOWN_SECONDS = 2.0  # Prevent re-triggering while chime plays
SILENCE_RMS_THRESHOLD = 60.0  # Energy gating threshold to save CPU during dead silence

def calculate_rms(data: np.ndarray) -> float:
    """Calculates Root Mean Square (RMS) amplitude of audio array."""
    if len(data) == 0:
        return 0.0
    return float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))

def setup_models(target_keyword: str = "hey_jarvis") -> Model:
    """
    Downloads models if needed and loads ONLY the specified keyword model
    to conserve RAM and CPU on the Raspberry Pi 3 B+.
    """
    print("==> Checking pre-trained openWakeWord models...")
    openwakeword.utils.download_models()

    all_paths = openwakeword.get_pretrained_model_paths("onnx")
    
    # Filter for target model
    selected_paths = [p for p in all_paths if target_keyword in os.path.basename(p)]
    if not selected_paths:
        print(f"[WARN] Target '{target_keyword}' not found, falling back to all available models.")
        selected_paths = all_paths

    print(f"==> Loading targeted model: {[os.path.basename(p) for p in selected_paths]}")
    oww_model = Model(wakeword_models=selected_paths, inference_framework="onnx")
    print(f"==> Active Wake Word: {list(oww_model.models.keys())}")
    return oww_model

def run_listener(keyword: str = "hey_jarvis", threshold: float = DEFAULT_THRESHOLD):
    # Initialize Model and Chime Player
    oww_model = setup_models(target_keyword=keyword)
    player = AudioPlayer()

    # Initialize PyAudio
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK_SIZE,
    )

    active_model_name = list(oww_model.models.keys())[0] if oww_model.models else keyword

    print("=" * 65)
    print(" Pi Google Home — Local Wake Word Engine Online")
    print(f" Active Trigger Model:  {active_model_name}")
    print(f" Detection Threshold:   {threshold:.2f}")
    print(" Speak into your JOUNIVO microphone to test!")
    print(" Press Ctrl+C to stop.")
    print("=" * 65)

    last_trigger_time = 0.0
    inference_times = []

    try:
        while True:
            # 1. Read 80ms audio chunk from USB Microphone
            audio_raw = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            audio_data = np.frombuffer(audio_raw, dtype=np.int16)
            rms = calculate_rms(audio_data)

            # 2. Energy gating: If dead silent, skip heavy inference to idle at <2% CPU
            if rms < SILENCE_RMS_THRESHOLD:
                status = f"\r[Idle (Quiet)] Mic RMS: {rms:4.1f} | Waiting for voice..."
                print(status, end="", flush=True)
                # Keep audio features buffer synchronized with silence
                oww_model.preprocessor.audio_buffer.extend(audio_data)
                continue

            # 3. Neural inference
            t0 = time.perf_counter()
            predictions = oww_model.predict(audio_data)
            dt = (time.perf_counter() - t0) * 1000.0  # in ms
            inference_times.append(dt)
            if len(inference_times) > 30:
                inference_times.pop(0)

            # 4. Detection check
            now = time.time()
            score = predictions.get(active_model_name, 0.0)
            avg_dt = sum(inference_times) / max(len(inference_times), 1)

            if now - last_trigger_time > COOLDOWN_SECONDS:
                if score >= threshold:
                    last_trigger_time = now
                    print(f"\n\n{'*' * 60}")
                    print(f" [TRIGGER DETECTED] >>> {active_model_name} <<<")
                    print(f" Confidence Score: {score:.3f} | Latency: {avg_dt:.1f}ms")
                    print(f"{'*' * 60}\n")
                    
                    # Play wake acknowledgment chime through 15" HDMI monitor speakers
                    try:
                        player.play_chime("wake.wav")
                    except Exception as e:
                        print(f"[ERROR] Failed to play chime: {e}")

                    print("Resuming listener...\n")
                    continue

            # Live terminal status
            status = f"\r[Active] Score: {score:4.2f}/{threshold:.2f} | Mic RMS: {rms:5.1f} | Latency: {avg_dt:4.1f}ms/80ms ({avg_dt/80.0*100:2.0f}% CPU)"
            print(status, end="", flush=True)

    except KeyboardInterrupt:
        print("\n\nStopping listener...")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
        player.close()
        print("Listener stopped cleanly.")

def main():
    parser = argparse.ArgumentParser(description="Pi Google Home Local Wake Word Listener")
    parser.add_argument("--keyword", type=str, default="hey_jarvis", help="Wake word keyword to load (hey_jarvis, alexa, hey_mycroft)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="Detection score threshold (0.0 to 1.0)")
    args = parser.parse_args()

    run_listener(keyword=args.keyword, threshold=args.threshold)

if __name__ == "__main__":
    main()
