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

## Deployment status
| Target | Change | Restarted |
|---|---|---|
| Pi client | #1 | `assistant-client` restart |
| Pi display | #2 | `smart-display` restart |
| Host server | #3, #4 | gateway relaunched (PID confirmed listening on 8765) |