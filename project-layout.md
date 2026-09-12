# Project Layout & Architecture

This document defines the structural architecture, component boundaries, and directory layout for the **Pi Google Home Assistant** system.

---

## 1. System Architecture Diagram

```
+-------------------------------------------------------------------------+
|                  Raspberry Pi 3 B+ (Arch Linux ARM)                     |
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
|            | (Audio Stream / Socket)      | (Audio Stream / State)      |
+------------|------------------------------|-----------------------------+
             |                              |
             |      Local Network (LAN)     |
             v                              |
+-------------------------------------------|-----------------------------+
|                  Host PC (Heavy-Lifting Server)                         |
|                                                                         |
|  +---------v------------------------------+----------+                  |
|  |              Gateway / Socket Server              |                  |
|  +----+---------------------+--------------------+---+                  |
|       |                     |                    |                      |
|       v                     v                    v                      |
|  +----+------------+   +----+------------+  +----+------------------+   |
|  | Speech-to-Text  |   | Reasoning / LLM |  | Text-to-Speech (TTS)  |   |
|  | (Whisper STT)   |   | Intent Engine   |  | (Piper Neural TTS)   |   |
|  +-----------------+   +-----------------+  +-----------------------+   |
|                                                                         |
+-------------------------------------------------------------------------+
```

---

## 2. Directory Layout

The repository will be structured cleanly into client (Pi), server (Host PC), shared contracts, and provisioning documentation:

```
pi-google-home/
├── .agents/                      # Agent rules and configuration
│   └── rules/
│       └── workflow.md           # Step-by-step enforcement rules
├── AGENTS.md                     # Root agent instructions & rules
├── GEMINI.md                     # Root agent instructions & rules (alias)
├── project-intent.md             # Project vision, hardware specs, and requirements
├── project-layout.md             # System architecture and directory organization
│
├── client/                       # Code running on Raspberry Pi 3 B+ (Arch Linux ARM)
│   ├── config/                   # Audio and environment configurations
│   │   ├── asound.conf           # ALSA routing (USB mic input, HDMI output)
│   │   └── client.env.example    # Host server address, audio device IDs
│   ├── audio/                    # Audio capture and playback abstractions
│   │   ├── capture.py            # Stream microphone input
│   │   └── playback.py           # Output synthesized voice & chimes via HDMI
│   ├── listener/                 # Wake word engine running on Pi
│   │   ├── wake_word.py          # Listener loop ("Hey Google" detection)
│   │   └── models/               # Model weights (openWakeWord / Porcupine / etc.)
│   ├── display/                  # GUI / Smart display presentation layer
│   │   ├── ui/                   # Web kiosk, Qt, or lightweight framebuffer UI
│   │   └── kiosk.sh              # Kiosk launcher script (X11 / Wayland / Cage)
│   ├── network/                  # Client-to-server networking & transport
│   │   └── client_transport.py   # WebSocket / gRPC communication client
│   └── systemd/                  # Systemd service units for auto-starting on Pi
│       ├── pi-assistant.service  # Main client assistant daemon
│       └── pi-display.service    # Kiosk display manager daemon
│
├── server/                       # Code running on Host PC (Heavy lifting)
│   ├── config/                   # Server configuration & environment variables
│   │   └── server.env.example    # Server port, model configurations, API keys
│   ├── api/                      # Ingestion endpoints & WebSocket handler
│   │   ├── gateway.py            # Gateway handling real-time audio from Pi
│   │   └── routes.py             # REST/control endpoints
│   ├── stt/                      # Speech-to-Text processing
│   │   └── transcriber.py        # Whisper / faster-whisper transcription
│   ├── brain/                    # Reasoning, NLP, and LLM processing
│   │   ├── intent.py             # Intent classifier & prompt routing
│   │   └── context.py            # Conversation history and session state
│   ├── tts/                      # Text-to-Speech synthesis
│   │   └── synthesizer.py        # Neural TTS engine (Piper, etc.)
│   └── integrations/             # Smart home & service actions
│       ├── weather.py            # Weather forecast provider
│       ├── timer.py              # Alarms and timers
│       └── home_control.py       # Home Assistant / local device hooks
│
├── shared/                       # Shared protocol definitions & types
│   ├── protocol.py               # Message formats (JSON / Protobuf schemas)
│   └── constants.py              # Audio formats (16kHz 16-bit mono), ports, event types
│
└── docs/                         # Setup and operational guides
    ├── 01-arch-arm-pi3-setup.md  # Step-by-step Arch Linux ARM installation for Pi 3B+
    ├── 02-audio-calibration.md   # USB mic ALSA calibration & HDMI speaker setup
    ├── 03-wake-word-bench.md     # Wake word listener benchmarking on Cortex-A53
    └── 04-server-setup.md        # Host PC environment and model dependencies
```

---

## 3. Technology & Framework Selection

| Layer | Component | Selected Technology | Rationale |
|---|---|---|---|
| **Pi OS** | Operating System | Arch Linux ARM (`alarm`) | Minimal resource footprint, pure systemd, up-to-date packages. |
| **Pi Audio** | Sound Architecture | ALSA + PipeWire / PulseAudio | Direct hardware device mapping for USB Mic and HDMI audio sink. |
| **Pi Listener** | Wake Word Engine | `openWakeWord` or `pvporcupine` | Ultra-low idle CPU load on Cortex-A53, reliable "Hey Google" model. |
| **Pi Display** | Smart Display UI | Lightweight Web Kiosk (Chromium / Cage) or Python (PyQt/Kivy) | Hardware-accelerated UI rendering to 15" HDMI monitor. |
| **Transport** | Client $\leftrightarrow$ Server | WebSockets (Binary PCM) | Low-latency bi-directional streaming for audio and control states. |
| **Host STT** | Speech-to-Text | `faster-whisper` (CTranslate2) | High-speed local transcription on PC GPU/CPU. |
| **Host Brain** | Agent / LLM | Local LLM (Ollama/vLLM) / Gemini API | Deep reasoning, tool calling, and conversational intelligence. |
| **Host TTS** | Voice Synthesis | `piper-tts` | Ultra-fast, natural-sounding neural voice synthesis. |
