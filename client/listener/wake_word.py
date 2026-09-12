#!/usr/bin/env python3
"""
Pi Google Home — Local Wake Word Listener
Continuously listens on the USB Microphone using openWakeWord (ONNX Runtime).
Plays an acknowledgment chime via the 15" HDMI monitor speakers when triggered.
"""

import os
import sys
import time
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

def setup_models(models_to_load: list[str] | None = None) -> Model:
    """Ensures feature models are downloaded and initializes the openWakeWord Model."""
    print("==> Checking and downloading pre-trained openWakeWord models...")
    openwakeword.utils.download_models()

    if models_to_load:
        print(f"==> Loading targeted models: {models_to_load}")
        oww_model = Model(wakeword_models=models_to_load, inference_framework="onnx")
    else:
        print("==> Loading all available openWakeWord pre-trained models (ONNX)...")
        oww_model = Model(inference_framework="onnx")

    print(f"==> Active Wake Word Models: {list(oww_model.models.keys())}")
    return oww_model

def run_listener(threshold: float = DEFAULT_THRESHOLD, selected_models: list[str] | None = None):
    # Initialize Model and Chime Player
    oww_model = setup_models(selected_models)
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

    print("=" * 65)
    print(" Pi Google Home — Wake Word Detection Active")
    print(f" Listening for triggers: {', '.join(oww_model.models.keys())}")
    print(f" Confidence Threshold: {threshold:.2f}")
    print(" Say 'Hey Jarvis', 'Alexa', or 'Hey Mycroft' to test!")
    print(" Press Ctrl+C to stop.")
    print("=" * 65)

    last_trigger_time = 0.0
    inference_times = []

    try:
        while True:
            # 1. Read audio chunk from USB Microphone
            audio_raw = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            audio_data = np.frombuffer(audio_raw, dtype=np.int16)

            # 2. Benchmark inference time
            t0 = time.perf_counter()
            predictions = oww_model.predict(audio_data)
            dt = (time.perf_counter() - t0) * 1000.0  # in ms
            inference_times.append(dt)
            if len(inference_times) > 50:
                inference_times.pop(0)

            # 3. Check for wake word activations
            now = time.time()
            if now - last_trigger_time > COOLDOWN_SECONDS:
                for model_name, score in predictions.items():
                    if score >= threshold:
                        last_trigger_time = now
                        avg_dt = sum(inference_times) / len(inference_times)
                        print(f"\n[TRIGGER DETECTED] >>> {model_name} <<< (Confidence: {score:.3f} | Latency: {avg_dt:.1f}ms)")
                        
                        # Play wake acknowledgment chime through HDMI monitor speakers
                        try:
                            player.play_chime("wake.wav")
                        except Exception as e:
                            print(f"[ERROR] Failed to play chime: {e}")
                        
                        print("Waiting for next trigger...\n")
                        break

            # Live terminal status (refreshes in place)
            max_model = max(predictions, key=predictions.get)
            max_score = predictions[max_model]
            avg_dt = sum(inference_times) / max(len(inference_times), 1)
            status = f"\r[Listening...] Top: {max_model} ({max_score:.2f}) | Inference: {avg_dt:4.1f}ms/80ms ({avg_dt/80.0*100:3.0f}% CPU)"
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
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="Detection score threshold (0.0 to 1.0)")
    parser.add_argument("--models", nargs="*", default=None, help="Specific model names or paths to load")
    args = parser.parse_args()

    run_listener(threshold=args.threshold, selected_models=args.models)

if __name__ == "__main__":
    main()
