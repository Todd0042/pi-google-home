# Project Intent: Pi Google Home Assistant

## 1. Overview & Vision
The goal of this project is to build a DIY, highly capable "Google Home" / smart display assistant appliance using a **Raspberry Pi Model 3 B+** paired with external peripherals, operating as a thin client connected over the local network to a powerful companion server hosted on the primary Linux PC.

---

## 2. Hardware Architecture & Specifications

### Client Device (The Smart Display Appliance)
- **Computing Core**: Raspberry Pi Model 3 B+
  - CPU: Quad Core 1.4GHz Broadcom BCM2837B0, Cortex-A53 (64-bit)
  - RAM: 1GB LPDDR2 SDRAM
  - Connectivity: 2.4GHz / 5GHz IEEE 802.11 b/g/n/ac Wi-Fi, Gigabit Ethernet over USB 2.0 (300 Mbps max), Bluetooth 4.2
- **Audio Input**: USB Conference Microphone
  - Far-field voice capture with built-in hardware acoustic echo cancellation (AEC) and noise suppression.
  - Plugs directly into one of the Pi's USB 2.0 ports.
- **Audio Output & Visual Display**: 15" HDMI Monitor with Built-in Speakers
  - Connected via full-size HDMI to the Raspberry Pi.
  - Delivers both the visual interface / smart display output and audible assistant speech / media playback.
- **Operating System**: **Arch Linux ARM** (aarch64 / armv7h)
  - Minimal, lightweight, rolling-release Linux distribution providing low memory footprint and direct control over audio/video pipelines.

### Server Host (The Heavy Lifter)
- **Host Machine**: Primary Linux PC (current system).
- **Role**: Handles compute-intensive operations that exceed the Raspberry Pi 3 B+'s 1GB RAM and CPU limits, including:
  - Speech-to-Text (STT) inference (e.g., Whisper / faster-whisper)
  - Natural language reasoning, intent resolution, and LLM processing
  - Text-to-Speech (TTS) synthesis (e.g., Piper, Coqui, or cloud/local neural engines)
  - Skill execution, automation orchestration, and integration with third-party APIs / smart home systems

---

## 3. Core Functional Requirements

1. **Local Wake Word Detection on the Pi**:
   - The Pi runs an efficient, low-latency wake word listener service configured to detect **"Hey Google"** (or custom wake phrases).
   - Must run continuously with low CPU and memory overhead on the Pi 3 B+.
   - When triggered, provides visual/audio feedback and opens a capture pipeline.

2. **Network Streaming & Communication**:
   - Real-time low-latency audio capture and transmission from Pi to the host PC server upon wake word trigger.
   - Server processes speech, evaluates intent, and streams back synthesized audio + display payload data.

3. **Smart Display Interface**:
   - The 15" monitor presents an ambient information screen (clock, weather, status) when idle.
   - When activated, transitions to an active listening/thinking visual state.
   - Renders rich visual responses (answers, cards, timers, media controls) alongside spoken responses.

4. **Audio Routing**:
   - Default capture device: USB Conference Microphone (ALSA / PipeWire / PulseAudio).
   - Default playback device: HDMI Audio Out routed to the 15" monitor speakers.

---

## 4. Development & Execution Methodology

- **Step-by-Step Implementation**: The project is strictly developed one step at a time, keeping changes focused, testable, and verified before moving forward.
- **Continuous Alignment**: Each phase ends with verification and clear next-step recommendations.
