#!/usr/bin/env python3
"""
Pi Google Home — Ultra-Lightweight Native Pygame Smart Display
Runs natively on Linux DRM/KMS or Wayland (Cage) without Chromium or X11.
Optimized with surface caching for <3% CPU and ~30MB RAM.
"""

import os
import sys
import time
import json
import math
import signal
import asyncio
import threading
import datetime
import traceback
import urllib.request

# Default to direct DRM/KMS for maximum performance and zero compositor overhead
if "SDL_VIDEODRIVER" not in os.environ:
    os.environ["SDL_VIDEODRIVER"] = "kmsdrm"

import pygame

# Configuration
SERVER_HOST = os.getenv("SERVER_HOST", "192.168.1.236")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8765"))
WEATHER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/api/weather"
WS_DISPLAY_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}/ws/display"

# Colors (Modern Deep Midnight Theme)
BG_COLOR = (11, 15, 25)
CARD_BG = (18, 26, 42)
CARD_BORDER = (35, 48, 75)
TEXT_PRIMARY = (245, 247, 250)
TEXT_SECONDARY = (148, 163, 184)
TEXT_MUTED = (100, 116, 139)
ACCENT_CYAN = (14, 165, 233)
ACCENT_BLUE = (59, 130, 246)
ACCENT_GREEN = (16, 185, 129)
ACCENT_AMBER = (245, 158, 11)
ACCENT_PURPLE = (139, 92, 246)

# State Colors mapping
STATE_COLORS = {
    "ready": ACCENT_GREEN,
    "idle": ACCENT_GREEN,
    "listening": ACCENT_BLUE,
    "thinking": ACCENT_AMBER,
    "speaking": ACCENT_PURPLE,
}

class SmartDisplayApp:
    def __init__(self):
        pygame.init()
        pygame.font.init()
        pygame.mouse.set_visible(False)

        # Detect display mode & resolution
        info = pygame.display.Info()
        self.w = info.current_w or 1280
        self.h = info.current_h or 720

        print(f"[DISPLAY] Initializing Native Smart Display at {self.w}x{self.h}...")
        self.screen = pygame.display.set_mode((self.w, self.h), pygame.FULLSCREEN | pygame.DOUBLEBUF)
        pygame.display.set_caption("Pi Google Home Smart Display")
        self.clock = pygame.time.Clock()

        # Scale factor relative to 1280x720 reference
        self.scale_x = self.w / 1280.0
        self.scale_y = self.h / 720.0
        self.scale = min(self.scale_x, self.scale_y)

        # Fonts
        font_family = "DejaVu Sans,Liberation Sans,Arial,sans-serif"
        self.font_huge = pygame.font.SysFont(font_family, int(84 * self.scale), bold=True)
        self.font_large = pygame.font.SysFont(font_family, int(46 * self.scale), bold=True)
        self.font_med = pygame.font.SysFont(font_family, int(28 * self.scale), bold=True)
        self.font_body = pygame.font.SysFont(font_family, int(22 * self.scale))
        self.font_small = pygame.font.SysFont(font_family, int(18 * self.scale))

        # Dynamic Assistant State
        self.assistant_state = "ready"
        self.transcription = ""
        self.assistant_reply = ""
        self.last_speech_time = 0.0

        # Weather Data & State
        self.weather_data = None
        self.weather_dirty = True

        # Pre-allocated Cached Clock Surfaces
        self.cached_time_str = ""
        self.cached_time_surf = None
        self.cached_ampm_surf = None
        self.cached_date_str = ""
        self.cached_date_surf = None
        self.loc_surf = self.font_small.render("Jacksonville, Florida", True, TEXT_MUTED)

        # Weather Card Surface
        self.cw = int(420 * self.scale_x)
        self.ch = int(420 * self.scale_y)
        self.cx = int(50 * self.scale_x)
        self.cy = int(240 * self.scale_y)
        self.weather_card_surf = pygame.Surface((self.cw, self.ch), pygame.SRCALPHA)

        # Forecast Card Surface
        self.rx = int(self.w * 0.63)
        self.ry = int(45 * self.scale_y)
        self.rw = int(self.w - self.rx - 45 * self.scale_x)
        self.rh = int(self.h - 90 * self.scale_y)
        self.forecast_card_surf = pygame.Surface((self.rw, self.rh), pygame.SRCALPHA)

        # Pre-allocated Aura Surface for Jarvis Orb
        self.max_aura_r = int(140 * self.scale)
        self.aura_surf = pygame.Surface((self.max_aura_r * 2, self.max_aura_r * 2), pygame.SRCALPHA)

        self.running = True

        # 1. Dedicated Weather Polling Worker Thread
        self.weather_thread = threading.Thread(target=self._weather_worker, daemon=True)
        self.weather_thread.start()

        # 2. Real-time WebSocket Listener Thread
        self.ws_thread = threading.Thread(target=self._websocket_worker, daemon=True)
        self.ws_thread.start()

    def _weather_worker(self):
        """Continuously polls the weather API, retrying rapidly if initial fetch fails."""
        while self.running:
            success = self._fetch_weather_sync()
            if not success:
                # Retry in 5s if host server wasn't ready
                for _ in range(5):
                    if not self.running:
                        break
                    time.sleep(1)
            else:
                # Successfully fetched, wait 10 minutes for next poll
                for _ in range(600):
                    if not self.running:
                        break
                    time.sleep(1)

    def _fetch_weather_sync(self) -> bool:
        """Fetches live weather JSON from host server synchronously."""
        try:
            req = urllib.request.Request(WEATHER_URL, headers={"User-Agent": "PiSmartDisplay/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    if data.get("success"):
                        self.weather_data = data
                        self.weather_dirty = True
                        print(f"[WEATHER] Successfully updated: {data.get('current', {}).get('temp')}°F, {data.get('current', {}).get('condition')}", flush=True)
                        return True
        except Exception as e:
            print(f"[WEATHER] Fetch error ({WEATHER_URL}): {e}", flush=True)
        return False

    def _websocket_worker(self):
        """Runs the asyncio WebSocket client loop in a background thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._websocket_listener())

    async def _websocket_listener(self):
        """Maintains persistent WebSocket connection to server for real-time assistant events."""
        import websockets
        while self.running:
            try:
                print(f"[WS] Connecting to {WS_DISPLAY_URL}...", flush=True)
                async with websockets.connect(WS_DISPLAY_URL, ping_interval=20, ping_timeout=10) as ws:
                    print("[WS] Connected to dashboard event stream!", flush=True)
                    while self.running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        msg_type = data.get("type")
                        payload = data.get("payload", {})

                        if msg_type == "state_change":
                            raw_state = str(payload.get("state", "ready")).lower()
                            if "listen" in raw_state:
                                self.assistant_state = "listening"
                            elif "think" in raw_state:
                                self.assistant_state = "thinking"
                            elif "speak" in raw_state:
                                self.assistant_state = "speaking"
                            else:
                                self.assistant_state = "ready"

                            if self.assistant_state in ("listening", "thinking", "speaking"):
                                self.last_speech_time = time.time()
                            print(f"[EVENT] State -> {self.assistant_state}", flush=True)

                        elif msg_type == "transcription":
                            self.transcription = str(payload.get("text", "")).strip()
                            self.last_speech_time = time.time()
                            print(f"[EVENT] User Transcription: \"{self.transcription}\"", flush=True)

                        elif msg_type == "assistant_reply":
                            self.assistant_reply = str(payload.get("text", "")).strip()
                            self.last_speech_time = time.time()
                            print(f"[EVENT] Assistant Reply: \"{self.assistant_reply}\"", flush=True)

                        elif msg_type == "weather_update":
                            self.weather_data = payload
                            self.weather_dirty = True

            except Exception as e:
                print(f"[WS] Connection dropped ({e}). Reconnecting in 3s...", flush=True)
                await asyncio.sleep(3)

    def draw_card(self, target_surf, rect, bg=CARD_BG, border=CARD_BORDER, radius=20):
        """Draws a sleek rounded card with a soft border on the target surface."""
        r = max(4, int(radius * self.scale))
        pygame.draw.rect(target_surf, bg, rect, border_radius=r)
        pygame.draw.rect(target_surf, border, rect, width=max(1, int(1.5 * self.scale)), border_radius=r)

    def draw_clock_section(self):
        """Renders the digital clock, date, and location badge using surface caching."""
        now = datetime.datetime.now()
        hour = now.hour % 12
        if hour == 0:
            hour = 12
        time_str = f"{hour}:{now.minute:02d}"
        date_str = now.strftime("%A, %B %d, %Y")

        if time_str != self.cached_time_str or not self.cached_time_surf:
            self.cached_time_str = time_str
            self.cached_time_surf = self.font_huge.render(time_str, True, TEXT_PRIMARY)
            ampm = "AM" if now.hour < 12 else "PM"
            self.cached_ampm_surf = self.font_med.render(ampm, True, ACCENT_CYAN)

        if date_str != self.cached_date_str or not self.cached_date_surf:
            self.cached_date_str = date_str
            self.cached_date_surf = self.font_body.render(date_str, True, TEXT_SECONDARY)

        x = int(50 * self.scale_x)
        y = int(45 * self.scale_y)
        self.screen.blit(self.cached_time_surf, (x, y))
        self.screen.blit(self.cached_ampm_surf, (x + self.cached_time_surf.get_width() + int(12 * self.scale_x), y + int(36 * self.scale_y)))
        self.screen.blit(self.cached_date_surf, (x, y + self.cached_time_surf.get_height() - int(4 * self.scale_y)))
        self.screen.blit(self.loc_surf, (x, y + self.cached_time_surf.get_height() + self.cached_date_surf.get_height() + int(2 * self.scale_y)))

    def _render_weather_card_surface(self):
        """Re-renders the weather card surface only when weather changes."""
        self.weather_card_surf.fill((0, 0, 0, 0))
        card_rect = pygame.Rect(0, 0, self.cw, self.ch)
        self.draw_card(self.weather_card_surf, card_rect)

        if not self.weather_data:
            loading_surf = self.font_body.render("Connecting to weather service...", True, TEXT_MUTED)
            self.weather_card_surf.blit(loading_surf, (int(30 * self.scale_x), int(40 * self.scale_y)))
            return

        current = self.weather_data.get("current", {})
        temp = current.get("temp", "--")
        feels_like = current.get("feels_like", "--")
        high = current.get("high", "--")
        low = current.get("low", "--")
        condition = current.get("condition", "Fair")
        rain_prob = current.get("rain_prob", 0)
        humidity = current.get("humidity", 0)
        wind_speed = current.get("wind_speed", 0)

        # Temp hero
        temp_surf = self.font_huge.render(f"{temp}°", True, TEXT_PRIMARY)
        self.weather_card_surf.blit(temp_surf, (int(30 * self.scale_x), int(25 * self.scale_y)))

        # Feels like badge
        feels_surf = self.font_small.render(f"Feels like {feels_like}°", True, TEXT_SECONDARY)
        self.weather_card_surf.blit(feels_surf, (int(35 * self.scale_x), int(125 * self.scale_y)))

        # Condition
        cond_surf = self.font_large.render(str(condition), True, ACCENT_CYAN)
        self.weather_card_surf.blit(cond_surf, (int(30 * self.scale_x), int(175 * self.scale_y)))

        # High / Low
        hl_surf = self.font_body.render(f"High: {high}°   Low: {low}°", True, TEXT_PRIMARY)
        self.weather_card_surf.blit(hl_surf, (int(30 * self.scale_x), int(245 * self.scale_y)))

        # Divider & metrics
        detail_y = int(310 * self.scale_y)
        pygame.draw.line(self.weather_card_surf, CARD_BORDER, (int(25 * self.scale_x), detail_y), (self.cw - int(25 * self.scale_x), detail_y), max(1, int(1 * self.scale)))

        metrics = [
            (f"Rain: {rain_prob}%", ACCENT_BLUE),
            (f"Hum: {humidity}%", TEXT_SECONDARY),
            (f"Wind: {wind_speed}mph", TEXT_SECONDARY),
        ]
        col_w = self.cw / 3.0
        for i, (m_text, m_color) in enumerate(metrics):
            m_surf = self.font_small.render(m_text, True, m_color)
            mx = int(i * col_w + (col_w - m_surf.get_width()) / 2)
            self.weather_card_surf.blit(m_surf, (mx, detail_y + int(35 * self.scale_y)))

    def _render_forecast_card_surface(self):
        """Re-renders the 7-day forecast surface only when weather changes."""
        self.forecast_card_surf.fill((0, 0, 0, 0))
        card_rect = pygame.Rect(0, 0, self.rw, self.rh)
        self.draw_card(self.forecast_card_surf, card_rect, radius=22)

        head_surf = self.font_med.render("7-Day Forecast", True, ACCENT_CYAN)
        self.forecast_card_surf.blit(head_surf, (int(30 * self.scale_x), int(30 * self.scale_y)))

        line_y = int(75 * self.scale_y)
        pygame.draw.line(self.forecast_card_surf, CARD_BORDER, (int(25 * self.scale_x), line_y), (self.rw - int(25 * self.scale_x), line_y), max(1, int(1 * self.scale)))

        daily = (self.weather_data or {}).get("daily", [])
        if not daily:
            none_surf = self.font_body.render("Forecast loading...", True, TEXT_MUTED)
            self.forecast_card_surf.blit(none_surf, (int(30 * self.scale_x), int(100 * self.scale_y)))
            return

        row_y = line_y + int(20 * self.scale_y)
        row_h = (self.rh - int(115 * self.scale_y)) / max(len(daily[:6]), 1)

        for day in daily[:6]:
            d_name = str(day.get("day_name", day.get("short_name", "Day")))
            d_high = day.get("high", "--")
            d_low = day.get("low", "--")
            d_cond = str(day.get("condition", "Clear"))
            d_rain = day.get("rain_prob", 0)

            day_surf = self.font_body.render(d_name, True, TEXT_PRIMARY)
            self.forecast_card_surf.blit(day_surf, (int(30 * self.scale_x), int(row_y + 6 * self.scale_y)))

            cond_surf = self.font_small.render(d_cond, True, TEXT_SECONDARY)
            self.forecast_card_surf.blit(cond_surf, (int(140 * self.scale_x), int(row_y + 8 * self.scale_y)))

            if d_rain > 0:
                rain_surf = self.font_small.render(f"Rain: {d_rain}%", True, ACCENT_BLUE)
                self.forecast_card_surf.blit(rain_surf, (self.rw - int(180 * self.scale_x), int(row_y + 8 * self.scale_y)))

            hl_surf = self.font_body.render(f"{d_high}° / {d_low}°", True, TEXT_PRIMARY)
            self.forecast_card_surf.blit(hl_surf, (self.rw - hl_surf.get_width() - int(25 * self.scale_x), int(row_y + 6 * self.scale_y)))

            row_y += row_h

    def draw_weather_section(self):
        """Blits the pre-rendered weather card (0% CPU cost)."""
        if self.weather_dirty:
            self._render_weather_card_surface()
            self._render_forecast_card_surface()
            self.weather_dirty = False
        self.screen.blit(self.weather_card_surf, (self.cx, self.cy))

    def draw_jarvis_orb(self):
        """Draws the animated pulsing Jarvis voice orb."""
        center_x = int(self.w * 0.50)
        center_y = int(self.h * 0.46)
        t = time.time()
        state_color = STATE_COLORS.get(self.assistant_state, ACCENT_GREEN)

        if self.assistant_state == "listening":
            pulse = math.sin(t * 8.0) * 14.0 * self.scale
        elif self.assistant_state == "thinking":
            pulse = math.sin(t * 5.0) * 8.0 * self.scale
        elif self.assistant_state == "speaking":
            pulse = math.sin(t * 10.0) * 18.0 * self.scale
        else:
            pulse = math.sin(t * 2.0) * 5.0 * self.scale

        base_r = max(10, int((52 + pulse) * self.scale))

        # 1. Outer Glow Aura (drawn on dedicated alpha surface)
        aura_r = min(int(base_r * 1.6), self.max_aura_r - 2)
        self.aura_surf.fill((0, 0, 0, 0))
        pygame.draw.circle(self.aura_surf, (*state_color, 45), (self.max_aura_r, self.max_aura_r), aura_r)
        self.screen.blit(self.aura_surf, (center_x - self.max_aura_r, center_y - self.max_aura_r))

        # 2. Outer Ring (drawn directly on display surface using solid RGB)
        pygame.draw.circle(self.screen, state_color, (center_x, center_y), base_r + max(2, int(14 * self.scale)), max(1, int(2 * self.scale)))

        # 3. Inner Core
        pygame.draw.circle(self.screen, state_color, (center_x, center_y), base_r)

        # 4. Highlight Center Core
        pygame.draw.circle(self.screen, (255, 255, 255), (center_x, center_y), max(2, int(base_r * 0.35)))

        # State label
        state_labels = {
            "ready": "READY",
            "listening": "LISTENING...",
            "thinking": "THINKING...",
            "speaking": "JARVIS SPEAKING",
        }
        lbl_text = state_labels.get(self.assistant_state, "READY")
        lbl_surf = self.font_small.render(lbl_text, True, state_color)
        self.screen.blit(lbl_surf, (center_x - lbl_surf.get_width() // 2, center_y + int(105 * self.scale_y)))

    def draw_right_panel(self):
        """Renders either live voice interaction dialogue or the cached 7-day forecast."""
        is_speech_active = (time.time() - self.last_speech_time < 12.0) and bool(self.transcription or self.assistant_reply)

        if is_speech_active:
            # Voice Dialogue Card
            self.draw_card(self.screen, pygame.Rect(self.rx, self.ry, self.rw, self.rh), radius=22)
            
            head_surf = self.font_med.render("Assistant Dialogue", True, ACCENT_CYAN)
            self.screen.blit(head_surf, (self.rx + int(30 * self.scale_x), self.ry + int(30 * self.scale_y)))

            line_y = self.ry + int(75 * self.scale_y)
            pygame.draw.line(self.screen, CARD_BORDER, (self.rx + int(25 * self.scale_x), line_y), (self.rx + self.rw - int(25 * self.scale_x), line_y), max(1, int(1 * self.scale)))

            curr_y = line_y + int(25 * self.scale_y)

            if self.transcription:
                u_tag = self.font_small.render("YOU SAID", True, ACCENT_BLUE)
                self.screen.blit(u_tag, (self.rx + int(30 * self.scale_x), curr_y))
                curr_y += int(28 * self.scale_y)
                curr_y = self._render_wrapped_text(f"\"{self.transcription}\"", self.rx + int(30 * self.scale_x), curr_y, self.rw - int(60 * self.scale_x), self.font_body, TEXT_PRIMARY)
                curr_y += int(30 * self.scale_y)

            if self.assistant_reply:
                a_tag = self.font_small.render("JARVIS", True, ACCENT_PURPLE)
                self.screen.blit(a_tag, (self.rx + int(30 * self.scale_x), curr_y))
                curr_y += int(28 * self.scale_y)
                self._render_wrapped_text(self.assistant_reply, self.rx + int(30 * self.scale_x), curr_y, self.rw - int(60 * self.scale_x), self.font_body, (226, 232, 240))

        else:
            # Blit pre-rendered 7-day forecast card (0% CPU)
            self.screen.blit(self.forecast_card_surf, (self.rx, self.ry))

    def _render_wrapped_text(self, text, x, y, max_width, font, color):
        """Safe word-wrap renderer that normalizes newlines and avoids off-screen overflows."""
        clean_text = " ".join(str(text).replace("\r", " ").replace("\n", " ").split())
        words = clean_text.split(" ")
        lines = []
        curr_line = []

        for word in words:
            test_line = " ".join(curr_line + [word])
            if font.size(test_line)[0] < max_width:
                curr_line.append(word)
            else:
                if curr_line:
                    lines.append(" ".join(curr_line))
                curr_line = [word]
        if curr_line:
            lines.append(" ".join(curr_line))

        # Max 7 lines to prevent drawing out of bounds
        for line in lines[:7]:
            try:
                s = font.render(line, True, color)
                self.screen.blit(s, (x, y))
                y += s.get_height() + max(2, int(4 * self.scale_y))
            except Exception as e:
                print(f"[RENDER ERROR] font.render error: {e}", flush=True)
        return y

    def run(self):
        """Main rendering loop clocked at 30 FPS."""
        def sig_handler(signum, frame):
            self.running = False

        signal.signal(signal.SIGTERM, sig_handler)
        signal.signal(signal.SIGINT, sig_handler)

        print("[DISPLAY] Ultra-efficient display loop started at 30 FPS...", flush=True)
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        self.running = False

            # Clear screen
            self.screen.fill(BG_COLOR)

            # Draw elements
            self.draw_clock_section()
            self.draw_weather_section()
            self.draw_jarvis_orb()
            self.draw_right_panel()

            # Flip screen
            pygame.display.flip()
            self.clock.tick(30)

        pygame.quit()

if __name__ == "__main__":
    try:
        app = SmartDisplayApp()
        app.run()
    except Exception:
        err_msg = traceback.format_exc()
        print(f"[FATAL CRASH] {err_msg}", file=sys.stderr, flush=True)
        with open("/tmp/pygame_display_crash.log", "w") as f:
            f.write(err_msg)
        sys.exit(1)
