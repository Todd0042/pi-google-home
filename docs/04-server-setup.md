# Step 04: Host PC Server Setup & Streaming Architecture

This document details the heavy-lifting server hosted on the primary Linux PC, responsible for GPU-accelerated Speech-to-Text (STT), Natural Language Reasoning (LLM), and Neural Text-to-Speech (TTS).

---

## 1. Hardware & System Architecture

- **Host Machine**: Primary Linux PC (Arch Linux x86_64).
- **GPU Acceleration**: NVIDIA GeForce RTX 5060 Ti (CUDA 13.3 / cuBLAS 12 / cuDNN 9).
- **Network Interface**: `192.168.1.236:8765` on local LAN.
- **Client Interface**: Raspberry Pi 3 Model B+ (`192.168.1.237`).

---

## 2. Component Stack

| Layer | Technology | Model | Performance / Latency |
|---|---|---|---|
| **STT** | `faster-whisper` (CTranslate2) | `base.en` (float16 on CUDA) | **~18–35 ms** inference time |
| **Brain / Reasoning** | `IntentEngine` | Local fast intents + Gemini API | **~10–150 ms** response time |
| **TTS** | `piper-tts` | `en_US-lessac-medium` | **~80–100 ms** synthesis time |
| **Gateway** | FastAPI + WebSockets | Binary PCM + JSON Events | Low latency bi-directional streaming |

---

## 3. WebSocket Streaming Protocol (`/ws/assistant`)

1. **Wake Event**: Client detects wake word and sends `{"type": "wake_triggered"}`.
2. **Audio Streaming**: Client streams raw 16kHz 16-bit mono PCM chunks as binary WebSocket frames.
3. **Speech End**: Client VAD detects silence and sends `{"type": "speech_end"}`.
4. **Transcription**: Server transcribes audio and sends `{"type": "transcription", "payload": {"text": "..."}}`.
5. **Assistant Response**: Server resolves intent / LLM reasoning and sends `{"type": "assistant_reply", "payload": {"text": "..."}}`.
6. **Voice Return**: Server streams synthesized WAV audio chunk and sends `{"type": "state_change", "payload": {"state": "IDLE"}}`.

---

## 4. Running the Server

Start the gateway server on the host PC:

```bash
./scripts/run_server.sh
```

Or run directly via the dedicated virtual environment:
```bash
.venv-server/bin/python -m server.api.gateway
```

Health check verification:
```bash
curl http://localhost:8765/health
# Returns: {"status":"online","stt_device":"cuda","tts_voice":"en_US-lessac-medium"}
```
