# Session Changes

All changes below were made and deployed this session. The Pi (client + display) and the host PC (server) are both updated.

## 1. Fixed voice input (crash-loop) — `client/main.py`
- **Problem**: the client was silently crash-looping with `OSError: -9997 Invalid sample rate` and never reached the wake-word loop.
- **Cause**: an auto-detect block opened the JOUNIVO USB mic as a raw device (`hw:2,0`) at 16kHz, which that hardware rejects. It also bypassed the ALSA `plug` conversion in `/etc/asound.conf`.
- **Fix**: removed the device-index auto-detect. The mic now opens through the ALSA `default` capture, routed by `/etc/asound.conf` to `hw:MICROPHONE,0` with automatic 16kHz→48kHz conversion.
- **Result**: client starts cleanly, `[MIC TICK]` confirms live capture, no more restarts. (This also cleared up the Pi dropping off the network — it was thrashing in a restart loop.)

## 2. Display layout fix — `client/display/pygame_display.py`
- The hero "Today's Weather" card overlapped the top-left clock/date/location header text.
- Moved the hero down (`hero_y` 122 → 200) and made it shorter (`hero_h` 280 → 235); shifted the 7-day forecast section down (460) to match.
- Verified on the Pi's 1920x1080 display; `smart-display` restarted and reporting clean.

## 3. Faster query → answer pipeline — `server/brain/intent.py` + `server/api/gateway.py`
- **Gemini is now streamed**: `generate_content_stream` with `max_output_tokens=128` and `temperature=0.2`, replacing the single blocking call.
- `IntentEngine.process_stream()` yields each reply sentence as soon as it arrives (time-to-first-token, not end-of-generation).
- The gateway synthesizes each sentence with Piper **in a worker thread as it streams in**, sending that WAV to the Pi immediately instead of waiting for the whole reply.
- **Verified**: only `gemini-3.6-flash` is valid for this API key (`2.5/2.0/1.5-flash` are retired); free tier is capped at 20 requests/day for that model.

## 4. Zero-wait on Gemini daily quota — `server/brain/intent.py`
- On a 429 (quota exhausted) the engine now records the date in `server/brain/.gemini_quota_block` and skips Gemini entirely for the rest of that calendar day.
- Subsequent queries instantly use local fallbacks (Open-Meteo weather / DuckDuckGo + Wikipedia search) — no more waiting on per-query 429 errors.
- The block auto-clears at the next calendar day.
- **Note**: this file is runtime state; `server/brain/.gemini_quota_block` is gitignored.

## 5. Output volume pegged to maximum — Pi ALSA
- HDMI speaker sink is ALSA card `vc4hdmi`. Verifed `PCM` control at `255/255 [100%] [0.00dB]` and re-applied `amixer -c 1 sset PCM 100%`.
- The 78% mixer found earlier belongs to the *unused* headphone jack (`bcm2835` card 0), not the HDMI monitor.

## 6. Local voice commands — `shared/protocol.py`, `server/brain/intent.py`, `server/api/gateway.py`, `client/main.py`, `client/network/client_transport.py`, `client/display/pygame_display.py`
- New `command` WebSocket event type: server detects a device command in the transcript, sends a `command` payload to the Pi client, then streams a voiced confirmation through the normal TTS path.
- Commands parse in `IntentEngine.process_stream()` (before weather/LLM) via `_match_system_command()`:
  - `reboot` / `restart` → client runs `sudo systemctl reboot` (delayed ~5s so the confirmation finishes) — **inactive until passwordless sudo is added** on the Pi.
  - `volume up` / `volume down` → client runs `amixer -c 1 sset PCM 5%+` / `5%-`.
  - `set volume to XX` → `amixer -c 1 sset PCM XX%` (clamped 0-100; numbers spoken as words via `_int_to_words`).
  - `display off` / `display on` → smart-display blanks/restores its own KMSDRM output (no `vcgencmd` under mainline KMS).
- `process()` now filters out command dicts; confirmation sentences are spoken like any reply.
- `scripts/run_server.sh` now launches Python with `-u` so server logs are unbuffered.

## 7. Verified end-to-end (live pipeline: Piper speech → WS → Whisper → intent → command → confirmation)
- `tests` extended via `test_commands_e2e.py`: **5/5** command flows pass (`display off/on`, `volume up/down`, `set volume to 45`); STT confidence 1.00.
- Caught & fixed a real bug during testing: the gateway drainer assumed all queue items were 3-tuples while command items were 2-tuples — command events crashed the handler. Commands now enqueue as uniform 3-tuples.
- Pi smart-display journal confirms `[EVENT] Display OFF/ON via voice command`.

## Deployment status
| Target | Change | Restarted |
|---|---|---|
| Pi client | #1 | `assistant-client` restart |
| Pi display | #2 | `smart-display` restart |
| Host server | #3, #4 | gateway relaunched (PID confirmed listening on 8765) |
| Pi client | #6 | `assistant-client` restart (NRestarts=0) |
| Pi display | #6 | `smart-display` restart (NRestarts=0) |
| Host server | #6, #7 | gateway relaunched via `scripts/run_server.sh` (unbuffered) |