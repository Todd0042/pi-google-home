#!/usr/bin/env python3
"""
Pi Google Home — Audio Loopback & Level Test
Verifies that the USB Microphone and HDMI Speakers function via Python/ALSA.
"""

import ctypes
import math
import struct
import sys
import pyaudio

# 1. Suppress noisy C-level ALSA error spew
try:
    ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(
        None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p
    )
    def py_error_handler(filename, line, function, err, fmt):
        pass
    c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
    asound = ctypes.cdll.LoadLibrary('libasound.so.2')
    asound.snd_lib_error_set_handler(c_error_handler)
except Exception:
    pass

# Audio Stream Parameters (Standard for Wake Word & STT)
RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK = 1024
RECORD_SECONDS = 3

def calculate_rms(data: bytes) -> float:
    """Calculates Root Mean Square (RMS) amplitude of PCM audio chunk."""
    count = len(data) // 2
    if count == 0:
        return 0.0
    shorts = struct.unpack(f"{count}h", data)
    sum_squares = sum(s * s for s in shorts)
    return math.sqrt(sum_squares / count)

def find_device_indices(p: pyaudio.PyAudio):
    """Finds input and output device indices."""
    input_idx = None
    output_idx = None

    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        name = dev.get("name", "")
        max_in = dev.get("maxInputChannels", 0)
        max_out = dev.get("maxOutputChannels", 0)

        # Look for explicit named devices or default
        if max_in > 0 and input_idx is None:
            if "MICROPHONE" in name or "mic" in name.lower() or "usb" in name.lower():
                input_idx = i
        if max_out > 0 and output_idx is None:
            if "vc4hdmi" in name or "hdmi" in name.lower() or "bcm2835" in name.lower():
                output_idx = i

    return input_idx, output_idx

def main():
    p = pyaudio.PyAudio()

    print("=" * 60)
    print(" Pi Google Home — Python Audio Verification")
    print(f" Target: {RATE} Hz | {CHANNELS} Channel (Mono) | 16-bit PCM")
    print("=" * 60)

    # Device enumeration
    in_idx, out_idx = find_device_indices(p)
    print(f"Device Discovery:")
    print(f" - Input device index:  {in_idx} ({p.get_device_info_by_index(in_idx)['name'] if in_idx is not None else 'Default ALSA'})")
    print(f" - Output device index: {out_idx} ({p.get_device_info_by_index(out_idx)['name'] if out_idx is not None else 'Default ALSA'})")

    # 1. Capture Test
    print(f"\n[1/2] Recording {RECORD_SECONDS} seconds from microphone...")
    print(">>> SPEAK INTO THE USB MICROPHONE NOW <<<")

    open_kwargs = {
        "format": FORMAT,
        "channels": CHANNELS,
        "rate": RATE,
        "input": True,
        "frames_per_buffer": CHUNK,
    }
    if in_idx is not None:
        open_kwargs["input_device_index"] = in_idx

    try:
        stream_in = p.open(**open_kwargs)
    except Exception as e:
        print(f"\n[INFO] Opening targeted input failed ({e}), falling back to default device...")
        open_kwargs.pop("input_device_index", None)
        stream_in = p.open(**open_kwargs)

    frames = []
    max_rms = 0.0

    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream_in.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        rms = calculate_rms(data)
        if rms > max_rms:
            max_rms = rms
        bars = "#" * min(int(rms / 100), 40)
        print(f"\rVolume: [{bars:<40}] (RMS: {rms:6.1f})", end="", flush=True)

    print(f"\nRecording complete! Peak RMS: {max_rms:.1f}")
    stream_in.stop_stream()
    stream_in.close()

    if max_rms < 50:
        print("[WARNING] Audio level is very low. Check microphone mute button or alsamixer.")
    else:
        print("[SUCCESS] Voice signal captured clearly from USB microphone.")

    # 2. Playback Test
    print("\n[2/2] Playing recorded audio back through 15\" HDMI monitor speakers...")
    play_kwargs = {
        "format": FORMAT,
        "channels": CHANNELS,
        "rate": RATE,
        "output": True,
        "frames_per_buffer": CHUNK,
    }
    if out_idx is not None:
        play_kwargs["output_device_index"] = out_idx

    try:
        stream_out = p.open(**play_kwargs)
    except Exception as e:
        print(f"\n[INFO] Opening targeted output failed ({e}), falling back to default device...")
        play_kwargs.pop("output_device_index", None)
        stream_out = p.open(**play_kwargs)

    for data in frames:
        stream_out.write(data)

    stream_out.stop_stream()
    stream_out.close()
    p.terminate()

    print("\n[SUCCESS] Audio playback completed.")
    print("=" * 60)

if __name__ == "__main__":
    main()
