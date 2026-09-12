#!/usr/bin/env python3
"""
Pi Google Home — Audio Playback Module
Handles playback of system chimes, alerts, and synthesized speech through HDMI.
"""

import os
import wave
import pyaudio

CHIME_DIR = os.path.join(os.path.dirname(__file__), "chimes")

class AudioPlayer:
    def __init__(self):
        self._pa = pyaudio.PyAudio()

    def play_wav(self, file_path: str):
        """Plays a WAV file through the default ALSA output."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        with wave.open(file_path, "rb") as wf:
            stream = self._pa.open(
                format=self._pa.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
            )
            chunk_size = 1024
            data = wf.readframes(chunk_size)
            while len(data) > 0:
                stream.write(data)
                data = wf.readframes(chunk_size)

            stream.stop_stream()
            stream.close()

    def play_wav_bytes(self, audio_bytes: bytes):
        """Plays WAV audio bytes directly from memory without disk I/O."""
        import io
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            stream = self._pa.open(
                format=self._pa.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
            )
            chunk_size = 2048
            data = wf.readframes(chunk_size)
            while len(data) > 0:
                stream.write(data)
                data = wf.readframes(chunk_size)

            stream.stop_stream()
            stream.close()

    def play_chime(self, chime_name: str = "wake.wav"):
        """Plays a system chime by filename from client/audio/chimes/."""
        path = os.path.join(CHIME_DIR, chime_name)
        self.play_wav(path)

    def play_chime_async(self, chime_name: str = "wake.wav"):
        """Plays chime in background thread so recording is not blocked or delayed."""
        import threading
        t = threading.Thread(target=self.play_chime, args=(chime_name,), daemon=True)
        t.start()

    def close(self):
        if self._pa:
            self._pa.terminate()
            self._pa = None

if __name__ == "__main__":
    player = AudioPlayer()
    print("Testing wake chime playback...")
    player.play_chime("wake.wav")
    player.close()
    print("Done.")
