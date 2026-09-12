#!/usr/bin/env python3
"""
Pi Google Home — Activation Chime Generator
Generates clean WAV tones for wake word trigger and confirmation feedback.
"""

import math
import os
import struct
import wave

CHIME_DIR = os.path.join(os.path.dirname(__file__), "chimes")
os.makedirs(CHIME_DIR, exist_ok=True)

def generate_tone(filename: str, freqs: list[tuple[float, float]], sample_rate: int = 48000, volume: float = 0.3):
    """
    Generates a multi-frequency chime with smooth attack/decay envelopes.
    freqs: list of (frequency_in_hz, duration_in_seconds)
    """
    path = os.path.join(CHIME_DIR, filename)
    total_samples = []

    for freq, duration in freqs:
        num_samples = int(sample_rate * duration)
        attack = int(num_samples * 0.1)
        decay = int(num_samples * 0.2)
        sustain = num_samples - attack - decay

        for i in range(num_samples):
            # Envelope calculation
            if i < attack:
                env = i / attack
            elif i < attack + sustain:
                env = 1.0
            else:
                env = 1.0 - (i - attack - sustain) / decay

            val = math.sin(2.0 * math.pi * freq * (i / sample_rate)) * env * volume
            sample = int(val * 32767.0)
            sample = max(-32768, min(32767, sample))
            total_samples.append(sample)

    with wave.open(path, "w") as wav:
        wav.setnchannels(1)  # Mono
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        data = struct.pack(f"<{len(total_samples)}h", *total_samples)
        wav.writeframes(data)

    print(f"[OK] Generated chime: {path}")

def main():
    # 1. Wake word detected chime: Rising friendly two-tone (523Hz C5 -> 659Hz E5)
    generate_tone("wake.wav", [(523.25, 0.10), (659.25, 0.15)], volume=0.35)

    # 2. Ready / listening chime: Quick crisp chirp
    generate_tone("ready.wav", [(880.0, 0.08)], volume=0.25)

    # 3. Error / cancel chime: Soft descending tone (440Hz -> 330Hz)
    generate_tone("cancel.wav", [(440.0, 0.10), (329.63, 0.18)], volume=0.30)

if __name__ == "__main__":
    main()
