# Step 02: Audio Hardware Calibration & ALSA Configuration

This guide documents the audio architecture, device identification, and ALSA configuration for the Pi Google Home client.

---

## 1. Identified Audio Hardware

- **Capture Device (Microphone)**:
  - Hardware: JOUNIVO USB Conference Microphone
  - ALSA Identifier: `card 2: MICROPHONE [JOUNIVO MICROPHONE], device 0: USB Audio`
  - ALSA Name: `MICROPHONE`
  - Native Format: 16kHz / 48kHz, 16-bit PCM

- **Playback Device (HDMI Speakers)**:
  - Hardware: 15" HDMI Monitor with built-in stereo speakers
  - ALSA Identifier: `card 0: vc4hdmi [vc4-hdmi], device 0: MAI PCM i2s-hifi-0`
  - ALSA Name: `vc4hdmi`
  - Protocol: Full-size HDMI audio sink

- **Analog Headphone Jack (Unused)**:
  - ALSA Identifier: `card 1: Headphones [bcm2835 Headphones]`

---

## 2. Permissions

Users accessing audio hardware must be members of the `audio` group:

```bash
sudo usermod -aG audio alarm
```

---

## 3. Permanent ALSA Default Routing (`/etc/asound.conf`)

To ensure applications (PyAudio, SoundDevice, OpenWakeWord, GStreamer, aplay/arecord) seamlessly capture from the USB mic and play to the HDMI speakers without hardcoded card numbers:

```alsa
# /etc/asound.conf
pcm.!default {
    type asym
    playback.pcm {
        type plug
        slave.pcm "hw:vc4hdmi,0"
    }
    capture.pcm {
        type plug
        slave {
            pcm "hw:MICROPHONE,0"
            channels 1
            rate 16000
            format S16_LE
        }
    }
}

ctl.!default {
    type hw
    card "vc4hdmi"
}
```

By referencing the hardware names (`vc4hdmi` and `MICROPHONE`) rather than numeric indexes (`0` and `2`), device routing remains stable across reboots even if USB enumeration order changes.

---

## 4. Verification Commands

Test default output (no card flags):
```bash
speaker-test -c 2 -t wav -l 1
```

Test default capture & loopback:
```bash
arecord -d 3 test_default.wav
aplay test_default.wav
```
