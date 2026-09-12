"""
Pi Google Home — Client Transport Module
Manages WebSocket connection and streaming protocols with the Host PC server.
"""

import json
import asyncio
import websockets
from typing import Optional, Callable, Awaitable

class AssistantClientTransport:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.ws: Optional[websockets.WebSocketClientProtocol] = None

    async def connect(self):
        """Connects to the server WebSocket endpoint."""
        self.ws = await websockets.connect(self.server_url)

    async def send_event(self, event_type: str, payload: dict | None = None):
        """Sends a JSON control event to the server."""
        if not self.ws:
            raise ConnectionError("WebSocket is not connected.")
        msg = {"type": event_type, "payload": payload or {}}
        await self.ws.send(json.dumps(msg))

    async def stream_audio_chunk(self, chunk: bytes):
        """Streams a raw binary PCM chunk to the server."""
        if not self.ws:
            raise ConnectionError("WebSocket is not connected.")
        await self.ws.send(chunk)

    async def receive_response(
        self,
        on_transcription: Optional[Callable[[str], None]] = None,
        on_reply: Optional[Callable[[str], None]] = None,
    ) -> bytes:
        """
        Listens for server events until TTS audio is received and turn completes.
        Returns the synthesized response WAV bytes.
        """
        if not self.ws:
            raise ConnectionError("WebSocket is not connected.")

        response_audio = bytearray()

        while True:
            msg = await self.ws.recv()
            if isinstance(msg, bytes):
                response_audio.extend(msg)
            else:
                data = json.loads(msg)
                event_type = data.get("type")
                payload = data.get("payload", {})

                if event_type == "transcription" and on_transcription:
                    on_transcription(payload.get("text", ""))
                elif event_type == "assistant_reply" and on_reply:
                    on_reply(payload.get("text", ""))
                elif event_type == "state_change" and payload.get("state") == "IDLE":
                    break

        return bytes(response_audio)

    async def close(self):
        if self.ws:
            await self.ws.close()
            self.ws = None
