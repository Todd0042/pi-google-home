# Pi Google Home — Project Rules & Engineering Guidelines

This repository contains the software and setup instructions for building a DIY Google Home / Smart Display appliance using a **Raspberry Pi Model 3 B+** (Arch Linux ARM) connected to a heavy-lifting server hosted on the user's primary Linux PC.

---

## Core Operational Rule: One Step at a Time & Propose Next Steps

### 1. Strictly One Step at a Time
- **Single Step Focus**: Execute implementations strictly one step at a time based on what the user has requested and laid out.
- **No Premature Implementation**: Do not jump ahead, do not combine multiple implementation phases into a single turn, and do not create unrequested components ahead of schedule.
- **Verification First**: Verify each step upon completion before proposing to move to the next phase.

### 2. Mandatory Next-Step Suggestions
- At the conclusion of every step and interaction, explicitly present clear, concise, and logical suggestions for the immediate next steps.
- Offer actionable choices so the user can steer the implementation pace and direction.

---

## Technical & Architectural Guidelines

### 1. Hardware & OS Guardrails
- **Client Device**: Raspberry Pi Model 3 B+ running **Arch Linux ARM**.
  - Respect the Pi 3 B+'s hardware limits (1GB RAM, Cortex-A53 quad-core).
  - Client processes must remain lightweight, memory-efficient, and low in idle CPU consumption.
- **Audio Capture**: USB Conference Microphone connected to the Pi (dedicated far-field input).
- **Audio & Video Sink**: 15" HDMI Monitor with built-in speakers (audio output + visual UI).
- **Wake Word Detection**: Local listener running directly on the Pi, trained/configured for **"Hey Google"** triggers.

### 2. Workload Segregation (Client vs. Server)
- **Pi Client Responsibilities**:
  - Audio capture from USB mic.
  - Wake-word listening loop.
  - Display UI rendering & HDMI speaker playback.
  - Network streaming of voice queries to the host server.
- **Host PC Server Responsibilities**:
  - Speech-to-Text (STT) inference.
  - Natural language reasoning / LLM processing.
  - Text-to-Speech (TTS) voice generation.
  - Heavy-lifting tasks and external API / home automation integrations.
