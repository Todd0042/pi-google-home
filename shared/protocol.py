"""
Pi Google Home — Shared Protocol Models
Defines message schemas for WebSocket client <-> server communication.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

@dataclass
class Message:
    type: str
    timestamp: float = field(default_factory=time.time)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "Message":
        obj = json.loads(data)
        return cls(
            type=obj["type"],
            timestamp=obj.get("timestamp", time.time()),
            payload=obj.get("payload", {}),
        )

# Event Types
class EventType:
    # Client -> Server
    WAKE_TRIGGERED = "wake_triggered"       # Wake word detected by client
    SPEECH_START = "speech_start"           # VAD detected start of speech
    SPEECH_END = "speech_end"               # VAD detected end of speech
    CLIENT_READY = "client_ready"           # Client connected and calibrated
    
    # Server -> Client
    STATE_CHANGE = "state_change"           # IDLE, LISTENING, THINKING, SPEAKING
    TRANSCRIPTION = "transcription"         # Recognized STT text (interim or final)
    ASSISTANT_REPLY = "assistant_reply"     # Final response text + display payload
    TTS_START = "tts_start"                 # Audio playback beginning
    TTS_END = "tts_end"                     # Audio playback completed
    ERROR = "error"                         # Error message
