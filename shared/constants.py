"""
Pi Google Home — Shared Constants
Common configurations for audio format, networking, and system events.
"""

# Audio Framing Standards (Universal across Client & Server)
AUDIO_SAMPLE_RATE = 16000     # 16 kHz
AUDIO_CHANNELS = 1            # Mono
AUDIO_SAMPLE_WIDTH = 2        # 16-bit (2 bytes per sample, signed little-endian)
AUDIO_CHUNK_SAMPLES = 1024    # Samples per streaming packet (64 ms @ 16kHz)
AUDIO_CHUNK_BYTES = AUDIO_CHUNK_SAMPLES * AUDIO_CHANNELS * AUDIO_SAMPLE_WIDTH  # 2048 bytes

# Network Ports & Defaults
DEFAULT_SERVER_PORT = 8765
DEFAULT_SERVER_HOST = "0.0.0.0"
WS_AUDIO_ENDPOINT = "/ws/audio"
WS_EVENTS_ENDPOINT = "/ws/events"

# Assistant State Machine
class AssistantState:
    IDLE = "IDLE"           # Ambient screen, listening for wake word
    LISTENING = "LISTENING" # Wake word triggered, recording user query
    THINKING = "THINKING"   # Query captured, server processing STT + LLM
    SPEAKING = "SPEAKING"   # Server streaming TTS audio, client playing back
    ERROR = "ERROR"         # An error occurred
