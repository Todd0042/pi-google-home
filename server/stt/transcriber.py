"""
Pi Google Home — Speech-to-Text (STT) Transcriber
GPU-accelerated audio transcription powered by faster-whisper (CTranslate2).
"""

import os
import sys
import io
import time
import ctypes
import numpy as np

# Dynamically load bundled nvidia CUDA libraries if present in virtualenv
try:
    import nvidia.cublas.lib
    cublas_dir = os.path.dirname(nvidia.cublas.lib.__file__)
    for lib in ["libcublasLt.so.12", "libcublas.so.12"]:
        p = os.path.join(cublas_dir, lib)
        if os.path.exists(p):
            ctypes.CDLL(p, mode=ctypes.RTLD_GLOBAL)
except Exception:
    pass

try:
    import nvidia.cudnn.lib
    cudnn_dir = os.path.dirname(nvidia.cudnn.lib.__file__)
    p = os.path.join(cudnn_dir, "libcudnn.so.9")
    if os.path.exists(p):
        ctypes.CDLL(p, mode=ctypes.RTLD_GLOBAL)
except Exception:
    pass

from faster_whisper import WhisperModel

class WhisperTranscriber:
    def __init__(
        self,
        model_size: str = "base.en",
        device: str = "cuda",
        compute_type: str = "float16",
    ):
        """
        Initializes faster-whisper on GPU (CUDA) or CPU fallback.
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        print(f"==> Loading Whisper STT Model: '{model_size}' on {device.upper()} ({compute_type})...")
        
        try:
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        except Exception as e:
            print(f"[WARN] Failed to load on {device} ({e}). Falling back to CPU...")
            self.device = "cpu"
            self.compute_type = "int8"
            self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

        print(f"==> Whisper STT Model ready on {self.device.upper()}.")

    def transcribe(self, audio_data: bytes | np.ndarray, sample_rate: int = 16000) -> str:
        """
        Transcribes 16kHz audio (raw 16-bit PCM bytes or float32 array) into text.
        """
        t0 = time.perf_counter()

        if isinstance(audio_data, bytes):
            # Convert 16-bit PCM to float32 in [-1.0, 1.0]
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            audio_np = audio_data.astype(np.float32)
            if audio_np.max() > 1.0 or audio_np.min() < -1.0:
                audio_np = audio_np / 32768.0

        segments, info = self.model.transcribe(
            audio_np,
            beam_size=5,
            language="en",
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        text_parts = [segment.text.strip() for segment in segments]
        transcription = " ".join(text_parts).strip()
        dt = (time.perf_counter() - t0) * 1000.0

        print(f"[STT] Transcribed ({dt:.1f}ms): \"{transcription}\" (Confidence: {info.language_probability:.2f})")
        return transcription

if __name__ == "__main__":
    # Quick self-test
    stt = WhisperTranscriber(model_size="tiny.en")
    print("Self-test: Passing 1 second of silence...")
    silence = np.zeros(16000, dtype=np.int16).tobytes()
    print("Result:", repr(stt.transcribe(silence)))
