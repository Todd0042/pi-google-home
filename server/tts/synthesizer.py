"""
Pi Google Home — Text-to-Speech (TTS) Synthesizer
High-speed neural voice synthesis powered by Piper TTS.
"""

import io
import os
import wave
import time
import requests
from pathlib import Path

VOICE_DIR = Path(__file__).parent / "voices"

# Piper Voice Assets on Hugging Face
VOICE_NAME = "en_US-lessac-medium"
ONNX_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/{VOICE_NAME}.onnx"
CONFIG_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/{VOICE_NAME}.onnx.json"

class PiperSynthesizer:
    def __init__(self, voice_name: str = VOICE_NAME):
        self.voice_name = voice_name
        self.model_path = VOICE_DIR / f"{voice_name}.onnx"
        self.config_path = VOICE_DIR / f"{voice_name}.onnx.json"
        self._ensure_voice_downloaded()
        
        from piper.voice import PiperVoice
        print(f"==> Loading Piper Neural Voice: {self.model_path}...")
        self.voice = PiperVoice.load(str(self.model_path), config_path=str(self.config_path))
        print("==> Piper TTS ready.")

    def _ensure_voice_downloaded(self):
        """Downloads the ONNX voice model and JSON config if not already cached."""
        VOICE_DIR.mkdir(parents=True, exist_ok=True)
        
        if not self.model_path.exists():
            print(f"==> Downloading Piper voice model ({VOICE_NAME}.onnx)...")
            res = requests.get(ONNX_URL, stream=True)
            res.raise_for_status()
            with open(self.model_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("Model downloaded.")

        if not self.config_path.exists():
            print(f"==> Downloading Piper voice config ({VOICE_NAME}.onnx.json)...")
            res = requests.get(CONFIG_URL)
            res.raise_for_status()
            with open(self.config_path, "wb") as f:
                f.write(res.content)
            print("Config downloaded.")

    def synthesize(self, text: str) -> bytes:
        """
        Synthesizes text into complete WAV audio bytes.
        """
        t0 = time.perf_counter()
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            self.voice.synthesize_wav(text, wav_file)

        audio_bytes = wav_buffer.getvalue()
        dt = (time.perf_counter() - t0) * 1000.0
        print(f"[TTS] Synthesized ({dt:.1f}ms, {len(audio_bytes)} bytes): \"{text[:40]}...\"")
        return audio_bytes

    def synthesize_pcm(self, text: str) -> bytes:
        """
        Synthesizes text into raw 16-bit PCM bytes (stripping WAV header)
        at Piper's native sample rate (typically 22050 Hz).
        """
        wav_bytes = self.synthesize(text)
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            return wf.readframes(wf.getnframes())

if __name__ == "__main__":
    tts = PiperSynthesizer()
    out = tts.synthesize("Hello! This is your Pi assistant speaking through Piper neural text to speech.")
    test_out = "server_test_speech.wav"
    with open(test_out, "wb") as f:
        f.write(out)
    print(f"Saved test speech to {test_out}")
