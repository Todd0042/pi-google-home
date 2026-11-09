<p align="center">
  <a href="https://ko-fi.com/todd0042">
    <img src="https://raw.githubusercontent.com/Todd0042/creator-assets/main/banners/todd_creator_banner_v1.0.png" alt="Support Todd on Ko-fi" width="100%" />
  </a>
</p>

---

# 🎙️ Pi Google Home — Distributed Smart Display & AI Voice Assistant Appliance

[![License: PolyForm Noncommercial](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-00f0ff.svg)](LICENSE)
[![Platform: Raspberry Pi + Linux](https://img.shields.io/badge/Platform-Raspberry%20Pi%203%20B%2B%20%7C%20Linux%20PC-orange.svg)]()
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-39ff14.svg)]()
[![STT: Whisper](https://img.shields.io/badge/STT-faster--whisper-blue.svg)]()
[![TTS: Piper Neural](https://img.shields.io/badge/TTS-Piper%20Neural-purple.svg)]()
[![Backend: FastAPI + WebSockets](https://img.shields.io/badge/Backend-FastAPI%20%2B%20WebSockets-teal.svg)]()
[![Support on Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Creator-F16061?style=flat&logo=ko-fi&logoColor=white)](https://ko-fi.com/todd0042)

> **A 100% private, self-hosted, distributed smart display voice assistant appliance. Pairs a lightweight Raspberry Pi 3 B+ edge client running Arch Linux ARM with a high-performance local Linux server host—delivering zero-cloud wake word detection, Whisper speech-to-text, LLM natural language intent parsing, Piper neural voice synthesis, and real-time kiosk display streaming over LAN.**

```
+-------------------------------------------------------------------------+
|                  Raspberry Pi 3 B+ (Arch Linux ARM Client)              |
|                                                                         |
|  +--------------------+        +---------------------+                  |
|  |  USB Conference    |        |  15" HDMI Monitor   |                  |
|  |  Microphone        |        |  (Display + Spkrs)  |                  |
|  +---------+----------+        +----------^----------+                  |
|            |                              |                             |
|            v                              | (HDMI Audio / Video)        |
|  +---------+----------+        +----------+----------+                  |
|  | Audio In (ALSA)    |        | Audio Out / UI Sink |                  |
|  +---------+----------+        +----------^----------+                  |
|            |                              |                             |
|            v                              |                             |
|  +---------+----------+        +----------+----------+                  |
|  | Wake Word Listener | -----> | Display & Playback  |                  |
|  | ("Hey Google")     |        | Controller          |                  |
|  +---------+----------+        +----------^----------+                  |
|            |                              |                             |
|            | (Binary PCM Stream)          | (Synthesized Audio / State) |
+------------|------------------------------|-----------------------------+
             |                              |
             |     Local Network (LAN WS)   |
             v                              |
+-------------------------------------------|-----------------------------+
|                  Host PC (Heavy-Lifting Server)                         |
|                                                                         |
|  +---------v------------------------------+----------+                  |
|  |              FastAPI WebSocket Gateway            |                  |
|  +----+---------------------+--------------------+---+                  |
|       |                     |                    |                      |
|       v                     v                    v                      |
|  +----+------------+   +----+------------+  +----+------------------+   |
|  | Speech-to-Text  |   | Reasoning / LLM |  | Text-to-Speech (TTS)  |   |
|  | (Faster-Whisper)|   | Intent Engine   |  | (Piper Neural TTS)    |   |
|  +-----------------+   +-----------------+  +-----------------------+   |
|                                                                         |
+-------------------------------------------------------------------------+
```

---

## 📖 Table of Contents

* **Part 1 — Appliance Overview & Quick Start**
  * [🎙️ What Is Pi Google Home?](#-what-is-pi-google-home)
  * [⚡ How a Voice Interaction Works in 3 Steps](#-how-a-voice-interaction-works-in-3-steps)
  * [📺 Smart Display Kiosk & Ambient HUD](#-smart-display-kiosk--ambient-hud)
  * [✨ Hardware & Software Highlights](#-hardware--software-highlights)
  * [🚀 Quick Setup & Deployment](#-quick-setup--deployment)
* **Part 2 — Consolidated Technical Documentation & Architecture Reference**
  * [1. Distributed Client-Server Topology & WebSocket Protocol (`shared/protocol.py`)](#1-distributed-client-server-topology--websocket-protocol)
  * [2. On-Device Low-Latency Wake Word Detection (`client/listener/wake_word.py`)](#2-on-device-low-latency-wake-word-detection)
  * [3. Real-Time Speech-to-Text with Faster-Whisper (`server/stt/transcriber.py`)](#3-real-time-speech-to-text-with-faster-whisper)
  * [4. LLM Intent Engine, Reasoning & Skill Dispatch (`server/brain/intent.py`)](#4-llm-intent-engine-reasoning--skill-dispatch)
  * [5. High-Fidelity Neural Voice Synthesis with Piper (`server/tts/synthesizer.py`)](#5-high-fidelity-neural-voice-synthesis-with-piper)
  * [6. Dual Kiosk Displays: Pygame & Web (`client/display/`, `server/display/`)](#6-dual-kiosk-displays-pygame--web)
  * [7. Automated Unit Verification Suite (`tests/`)](#7-automated-unit-verification-suite)
  * [8. Clean-Room Provenance & Non-Commercial Licensing](#8-clean-room-provenance--non-commercial-licensing)

---

# Part 1 — Appliance Overview & Quick Start

## 🎙️ What Is Pi Google Home?

Commercial smart speakers rely on always-on cloud servers, harvesting voice telemetry, logging conversation histories, and becoming obsolete when cloud vendors discontinue support.

**Pi Google Home** is an open-source, private, distributed smart display appliance that delivers the responsive utility of commercial smart displays while keeping **100% of audio and inference on your local network**:
1. **Edge Client Efficiency**: A Raspberry Pi 3 B+ handles continuous microphone listening, hardware wake word detection, audio capture, and full-screen kiosk rendering.
2. **Heavy-Lifting Server Host**: Runs GPU/CPU-accelerated Speech-to-Text (Faster-Whisper), neural voice synthesis (Piper), and local LLM intent routing on your home server or desktop PC.
3. **Low-Latency Streaming**: Audio is streamed in raw PCM chunks over persistent WebSockets with duplex state synchronization, achieving sub-second speech recognition and immediate spoken responses.

---

## ⚡ How a Voice Interaction Works in 3 Steps

1. **Wake Word Trigger**: Say *"Hey Google"* (or custom wake phrase). The Pi's on-device acoustic model triggers instantly, illuminates the visual listening indicator, and sounds an earcon chime.
2. **Audio Streaming & Transcription**: Your spoken command is streamed over WebSocket to the server host, where Faster-Whisper transcribes the audio with high acoustic accuracy.
3. **Reasoning & Neural Response**: The server intent engine resolves the query (weather, timers, system control, general knowledge via LLM), Piper synthesizes high-fidelity neural speech, and the Pi speaks the answer while rendering visual cards on the display.

---

## 📺 Smart Display Kiosk & Ambient HUD

The display dynamically transitions across states:
* **Idle Ambient State**: Displays a clean digital clock, local weather conditions, room status, and network connectivity indicators.
* **Listening State**: Animated glowing visualizer rings pulse in response to speech volume input.
* **Processing State**: Visual loader showing transcription confidence and skill execution.
* **Response State**: Card UI displaying formatted markdown, weather forecasts, web search summaries, or timer countdowns.

---

## ✨ Hardware & Software Highlights

* **🔒 100% Offline Privacy**: Zero external cloud APIs required. Speech recognition and speech synthesis execute completely on local hardware.
* **⚡ Split-Architecture Efficiency**: The Pi 3 B+ stays cool and responsive by offloading heavy model inference to the host server.
* **🎯 OpenWakeWord Integration**: Efficient on-device wake phrase detection with low false-positive rates.
* **🗣️ Piper Neural TTS**: Generates natural, human-like voice responses with negligible synthesis latency.
* **🛡️ Defensive System Resilience**: Includes automated watchdog scripts, ALSA input calibration, and auto-reconnecting WebSocket pipelines.

---

## 🚀 Quick Setup & Deployment

### 1. Server Setup (Host PC)
```bash
# Clone the repository
git clone https://github.com/Todd0042/pi-google-home.git
cd pi-google-home/server

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start the gateway server
python api/gateway.py
```

### 2. Client Setup (Raspberry Pi 3 B+)
```bash
cd pi-google-home/client

# Configure ALSA audio device
sudo cp config/asound.conf /etc/asound.conf

# Launch the client listener and display
python main.py --server-host 192.168.1.100 --server-port 8000
```

---

# Part 2 — Consolidated Technical Documentation & Architecture Reference

## 1. Distributed Client-Server Topology & WebSocket Protocol

Communication between the Raspberry Pi client and the host server uses binary and JSON frames over a persistent WebSocket connection:

```python
# Protocol frame types in shared/protocol.py
class FrameType(str, Enum):
    WAKE_TRIGGER   = "wake_trigger"   # Client -> Server: Wake word activated
    AUDIO_CHUNK    = "audio_chunk"    # Client -> Server: Raw PCM audio bytes (16kHz 16-bit mono)
    AUDIO_END      = "audio_end"      # Client -> Server: User finished speaking (VAD silence)
    TRANSCRIPTION  = "transcription"  # Server -> Client: Real-time recognized text
    INTENT_RESULT  = "intent_result"  # Server -> Client: Structured skill execution payload
    TTS_AUDIO      = "tts_audio"      # Server -> Client: Synthesized WAV/PCM response audio
    STATE_CHANGE   = "state_change"   # Bi-directional: IDLE, LISTENING, THINKING, SPEAKING
```

---

## 2. On-Device Low-Latency Wake Word Detection

Located in [`client/listener/wake_word.py`](client/listener/wake_word.py):
* Continuously reads 1280-sample chunks ($80\text{ ms}$) from ALSA audio input at $16\text{ kHz}$ mono.
* Uses openWakeWord quantized TFLite/ONNX models running on the Pi's Cortex-A53 CPU.
* Maintains a rolling ring buffer of pre-trigger audio so that initial speech syllables are never clipped when streaming begins.

---

## 3. Real-Time Speech-to-Text with Faster-Whisper

Located in [`server/stt/transcriber.py`](server/stt/transcriber.py):
* Uses CTranslate2-accelerated `faster-whisper` (`base.en` or `small.en`) on the host machine.
* Implements dynamic voice activity detection (VAD) filtering using Silero VAD to prune background acoustic noise.
* Emits intermediate transcription tokens to reduce perceived latency before final phrase closure.

---

## 4. LLM Intent Engine, Reasoning & Skill Dispatch

Located in [`server/brain/intent.py`](server/brain/intent.py):
* Directs queries through a multi-tier intent resolver:
  1. **Deterministic Built-in Skills**: Instant regex/slot matching for alarms, timers, weather, media controls, and volume adjustments.
  2. **LLM Knowledge & Assistant Engine**: Complex conversational queries are routed to local LLMs (via Ollama or local inference) with system-prompted JSON tool calling.
* Formats responses into concise, spoken-friendly conversational dialogue suitable for audio playback.

---

## 5. High-Fidelity Neural Voice Synthesis with Piper

Located in [`server/tts/synthesizer.py`](server/tts/synthesizer.py):
* Uses the lightweight `piper-tts` neural engine with high-quality English voice checkpoints (`en_US-lessac-medium` or `en_US-amy-medium`).
* Generates 22.05 kHz 16-bit mono WAV streams with near real-time synthesis factor ($RTF < 0.2$ on CPU).
* Streams generated audio chunks directly back to the Pi client for zero-gap playback.

---

## 6. Dual Kiosk Displays: Pygame & Web

The visual kiosk layer supports two runtime modes:
* **Native Pygame Framebuffer (`client/display/pygame_display.py`)**: Renders directly to Linux DRM/KMS or X11 on Arch Linux ARM without requiring a full desktop environment.
* **Modern Web Smart Display (`server/display/index.html`)**: HTML5/CSS3 interface accessible from any browser on your network, featuring responsive glassmorphism cards and live WebSocket visual telemetry.

---

## 7. Automated Unit Verification Suite

The repository includes test suites covering protocol contracts, gateway WebSocket events, and audio processing:
```bash
# Run server test suite
pytest tests/ -v
```
Tests in [`tests/test_gateway_ws.py`](tests/test_gateway_ws.py) verify full client-server handshakes, binary audio framing, and state transitions.

---

## 8. Clean-Room Provenance & Non-Commercial Licensing

Distributed under the **PolyForm Noncommercial License 1.0.0**.

Free for personal, creator, educational, and hobbyist use. For commercial deployment inquiries or custom licensing, contact [Todd.0042.git@gmail.com](mailto:Todd.0042.git@gmail.com).

---

<p align="center">
  If you find Pi Google Home useful for your local smart home setup, consider supporting development:<br/><br/>
  <a href="https://ko-fi.com/todd0042" target="_blank">
    <img src="https://img.shields.io/badge/☕_Support_on_Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white" alt="Support on Ko-fi">
  </a>
</p>

---

<p align="center">
  <a href="https://ko-fi.com/todd0042">
    <img src="https://raw.githubusercontent.com/Todd0042/creator-assets/main/banners/todd_creator_banner_v1.0.png" alt="Support Todd on Ko-fi" width="100%" />
  </a>
</p>
