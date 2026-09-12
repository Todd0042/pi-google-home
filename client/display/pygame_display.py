#!/usr/bin/env python3
"""
Pi Google Home — Ultra-Lightweight Native Pygame Smart Display
Faithfully reproduces the modern Glassmorphism Google Chrome CSS Dashboard
with zero-overhead DRM/KMS hardware rendering (<4% CPU, ~50MB RAM).
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

# Colors (Faithful to CSS --bg-primary, --bg-card, and color tokens)
BG_COLOR = (10, 13, 20)                 # #0a0d14
CARD_BG = (18, 24, 38)                  # rgba(18, 24, 38, 0.92)
CARD_BG_TODAY = (24, 34, 54)            # rgba(30, 42, 64, 0.70)
CARD_BORDER = (40, 50, 75)              # rgba(255, 255, 255, 0.08)
CARD_BORDER_TODAY = (56, 189, 248)      # #38bdf8

TEXT_PRIMARY = (240, 244, 252)          # #f0f4fc
TEXT_SECONDARY = (148, 163, 184)        # #94a3b8
TEXT_MUTED = (100, 116, 139)            # #64748b

# Accent & State Colors
ACCENT_READY = (16, 185, 129)           # #10b981 (Emerald Green)
ACCENT_LISTENING = (6, 182, 212)        # #06b6d4 (Electric Cyan)
ACCENT_THINKING = (245, 158, 11)        # #f59e0b (Amber / Gold)
ACCENT_SPEAKING = (139, 92, 246)        # #8b5cf6 (Vibrant Purple)

STATE_COLORS = {
    "ready": ACCENT_READY,
    "idle": ACCENT_READY,
    "listening": ACCENT_LISTENING,
    "thinking": ACCENT_THINKING,
    "querying": ACCENT_THINKING,
    "speaking": ACCENT_SPEAKING,
}

STATE_LABELS = {
    "ready": "READY",
    "idle": "READY",
    "listening": "LISTENING",
    "thinking": "THINKING",
    "querying": "THINKING",
    "speaking": "SPEAKING",
}

STATE_SUBTEXTS = {
    "ready": 'Say "Hey Jarvis"',
    "idle": 'Say "Hey Jarvis"',
    "listening": "Listening...",
    "thinking": "Thinking...",
    "querying": "Thinking...",
    "speaking": "Responding...",
}

TEMP_HOT = (248, 113, 113)              # #f87171
TEMP_COOL = (96, 165, 250)              # #60a5fa
ACCENT_BLUE = (59, 130, 246)
GOLDEN_SUN = (251, 191, 36)             # #fbbf24

class SmartDisplayApp:
    def __init__(self):
        pygame.display.init()
        pygame.font.init()
        try:
            pygame.mouse.set_visible(False)
        except Exception:
            pass

        # Detect resolution (e.g. 1920x1080 or 1280x720)
        info = pygame.display.Info()
        self.w = info.current_w or 1920
        self.h = info.current_h or 1080

        print(f"[DISPLAY] Initializing Native Smart Display at {self.w}x{self.h}...", flush=True)
        self.screen = pygame.display.set_mode((self.w, self.h), pygame.FULLSCREEN | pygame.DOUBLEBUF)
        pygame.display.set_caption("Pi Google Home Smart Display")

        # Scale relative to 1920x1080 desktop reference
        self.scale_x = self.w / 1920.0
        self.scale_y = self.h / 1080.0
        self.scale = min(self.scale_x, self.scale_y)

        # Fonts (scalable sizes based on 1920x1080 standard)
        font_family = "DejaVu Sans,Liberation Sans,Arial,sans-serif"
        self.font_giant = pygame.font.SysFont(font_family, int(112 * self.scale), bold=True)
        self.font_huge = pygame.font.SysFont(font_family, int(64 * self.scale), bold=True)
        self.font_large = pygame.font.SysFont(font_family, int(36 * self.scale), bold=True)
        self.font_med = pygame.font.SysFont(font_family, int(22 * self.scale), bold=True)
        self.font_body = pygame.font.SysFont(font_family, int(18 * self.scale))
        self.font_small = pygame.font.SysFont(font_family, int(15 * self.scale))
        self.font_tiny = pygame.font.SysFont(font_family, int(12 * self.scale), bold=True)

        # Dynamic Assistant State
        self.assistant_state = "ready"
        self.transcription = ""
        self.assistant_reply = ""
        self.last_speech_time = 0.0
        self.screen_active = True

        # Weather Cache
        self.weather_data = None
        self.weather_dirty = True

        # Pre-allocated Surface Caches
        self.pad_x = int(48 * self.scale_x)
        self.pad_y = int(32 * self.scale_y)

        # Hero Weather Panel: full width glass card
        self.hero_x = self.pad_x
        self.hero_y = int(200 * self.scale_y)
        self.hero_w = self.w - 2 * self.pad_x
        self.hero_h = int(235 * self.scale_y)
        self.hero_surf = pygame.Surface((self.hero_w, self.hero_h), pygame.SRCALPHA)

        # 7-Day Forecast Area
        self.forecast_y = int(460 * self.scale_y)
        self.forecast_cards_y = self.forecast_y + int(38 * self.scale_y)
        self.forecast_cards_h = self.h - self.forecast_cards_y - int(32 * self.scale_y)
        self.forecast_surf = pygame.Surface((self.hero_w, self.forecast_cards_h), pygame.SRCALPHA)

        # Pre-rendered clock cache
        self.cached_time_str = ""
        self.cached_time_surf = None
        self.cached_ampm_surf = None
        self.cached_date_str = ""
        self.cached_date_surf = None

        self.running = True

        # 1. Background Weather Worker Thread
        self.weather_thread = threading.Thread(target=self._weather_worker, daemon=True)
        self.weather_thread.start()

        # 2. Real-time WebSocket Event Listener Thread
        self.ws_thread = threading.Thread(target=self._websocket_worker, daemon=True)
        self.ws_thread.start()

    def _weather_worker(self):
        """Continuously polls the weather API, retrying rapidly on failure, then every 10 min."""
        while self.running:
            success = self._fetch_weather_sync()
            if not success:
                for _ in range(5):
                    if not self.running:
                        break
                    time.sleep(1)
            else:
                for _ in range(600):
                    if not self.running:
                        break
                    time.sleep(1)

    def _fetch_weather_sync(self) -> bool:
        """Fetches live weather JSON from host server."""
        try:
            req = urllib.request.Request(WEATHER_URL, headers={"User-Agent": "PiSmartDisplay/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.weather_data = data
                    self.weather_dirty = True
                    curr = data.get("current", {})
                    print(f"[WEATHER] Successfully updated: {curr.get('temp')}°F, {curr.get('condition')}", flush=True)
                    return True
        except Exception as e:
            print(f"[WEATHER] Fetch failed: {e}. Retrying soon...", flush=True)
        return False

    def _websocket_worker(self):
        """Asynchronous worker for persistent WebSocket event stream."""
        asyncio.run(self._websocket_loop())

    async def _websocket_loop(self):
        """Connects to server WebSocket and receives live state / dialogue events."""
        import websockets
        while self.running:
            try:
                print(f"[WS] Connecting to {WS_DISPLAY_URL}...", flush=True)
                async with websockets.connect(WS_DISPLAY_URL) as ws:
                    print("[WS] Connected to dashboard event stream!", flush=True)
                    while self.running:
                        msg_str = await ws.recv()
                        data = json.loads(msg_str)
                        msg_type = data.get("type")
                        payload = data.get("payload", {})

                        if msg_type == "state_change":
                            raw_state = str(payload.get("state", "ready")).lower()
                            if "listen" in raw_state:
                                self.assistant_state = "listening"
                            elif "think" in raw_state or "query" in raw_state:
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

                        elif msg_type == "command":
                            action = str(payload.get("action", ""))
                            if action == "display_off":
                                self.screen_active = False
                                print("[EVENT] Display OFF via voice command", flush=True)
                            elif action == "display_on":
                                self.screen_active = True
                                print("[EVENT] Display ON via voice command", flush=True)

                        elif msg_type == "weather_update":
                            self.weather_data = payload
                            self.weather_dirty = True

            except Exception as e:
                print(f"[WS] Connection dropped ({e}). Reconnecting in 3s...", flush=True)
                await asyncio.sleep(3)

    def draw_card(self, target_surf, rect, bg=CARD_BG, border=CARD_BORDER, radius=24, border_width=1):
        """Draws a sleek modern glassmorphism card with rounded corners."""
        r = max(4, int(radius * self.scale))
        pygame.draw.rect(target_surf, bg, rect, border_radius=r)
        pygame.draw.rect(target_surf, border, rect, width=max(1, int(border_width * self.scale)), border_radius=r)

    def draw_weather_symbol(self, target_surf, condition_str, center_x, center_y, size):
        """Draws a clean, stylized weather illustration (Sun, Cloud, Rain, Storm, Snow)."""
        cond = str(condition_str).lower()
        cx, cy = int(center_x), int(center_y)
        r = max(6, int(size * self.scale))

        if "clear" in cond or "sun" in cond or "fair" in cond:
            # Radiant Golden Sun
            pygame.draw.circle(target_surf, GOLDEN_SUN, (cx, cy), r)
            # Outer ray ring
            pygame.draw.circle(target_surf, (253, 224, 71), (cx, cy), r + max(3, int(4 * self.scale)), max(1, int(2 * self.scale)))

        elif "rain" in cond or "shower" in cond or "drizzle" in cond:
            # Cloud + Falling Rain Ticks
            cloud_color = (148, 163, 184)
            cr = int(r * 0.7)
            pygame.draw.circle(target_surf, cloud_color, (cx - int(cr * 0.6), cy - int(cr * 0.2)), int(cr * 0.7))
            pygame.draw.circle(target_surf, cloud_color, (cx + int(cr * 0.6), cy - int(cr * 0.1)), int(cr * 0.8))
            pygame.draw.circle(target_surf, (203, 213, 225), (cx, cy - int(cr * 0.5)), cr)
            # Rain drops
            rain_color = (56, 189, 248)
            drop_len = max(4, int(6 * self.scale))
            for offset_x in [-int(r * 0.5), 0, int(r * 0.5)]:
                start_p = (cx + offset_x, cy + int(cr * 0.8))
                end_p = (cx + offset_x - int(2 * self.scale), cy + int(cr * 0.8) + drop_len)
                pygame.draw.line(target_surf, rain_color, start_p, end_p, max(1, int(2 * self.scale)))

        elif "thunder" in cond or "storm" in cond:
            # Dark Storm Cloud + Lightning Zigzag
            cloud_color = (100, 116, 139)
            cr = int(r * 0.7)
            pygame.draw.circle(target_surf, cloud_color, (cx - int(cr * 0.6), cy - int(cr * 0.2)), int(cr * 0.7))
            pygame.draw.circle(target_surf, cloud_color, (cx + int(cr * 0.6), cy - int(cr * 0.1)), int(cr * 0.8))
            pygame.draw.circle(target_surf, (148, 163, 184), (cx, cy - int(cr * 0.5)), cr)
            # Lightning Bolt
            bolt_pts = [
                (cx - int(2 * self.scale), cy + int(cr * 0.4)),
                (cx + int(4 * self.scale), cy + int(cr * 0.8)),
                (cx, cy + int(cr * 0.8)),
                (cx + int(3 * self.scale), cy + int(cr * 1.5)),
            ]
            pygame.draw.lines(target_surf, (245, 158, 11), False, bolt_pts, max(2, int(2 * self.scale)))

        elif "snow" in cond or "ice" in cond:
            # Cloud + Snowflake dots
            cloud_color = (203, 213, 225)
            cr = int(r * 0.7)
            pygame.draw.circle(target_surf, cloud_color, (cx, cy - int(cr * 0.3)), cr)
            for offset_x in [-int(r * 0.4), int(r * 0.4)]:
                pygame.draw.circle(target_surf, (255, 255, 255), (cx + offset_x, cy + int(cr * 0.9)), max(2, int(2 * self.scale)))

        else:
            # Partly Cloudy / Overcast: Sun peeking behind Cloud
            sun_r = int(r * 0.65)
            pygame.draw.circle(target_surf, GOLDEN_SUN, (cx + int(sun_r * 0.8), cy - int(sun_r * 0.6)), sun_r)
            cloud_color = (148, 163, 184)
            cr = int(r * 0.65)
            pygame.draw.circle(target_surf, cloud_color, (cx - int(cr * 0.6), cy + int(cr * 0.1)), int(cr * 0.7))
            pygame.draw.circle(target_surf, cloud_color, (cx + int(cr * 0.4), cy + int(cr * 0.1)), int(cr * 0.8))
            pygame.draw.circle(target_surf, (203, 213, 225), (cx - int(cr * 0.1), cy - int(cr * 0.2)), cr)

    def draw_header_section(self):
        """Renders the top bar: Clock & Location on Left; Jarvis Helper Widget on Right."""
        now = datetime.datetime.now()
        hour = now.hour % 12
        if hour == 0:
            hour = 12
        time_str = f"{hour}:{now.minute:02d}"
        ampm = "AM" if now.hour < 12 else "PM"
        date_str = now.strftime("%A, %B %d, %Y")

        if time_str != self.cached_time_str or not self.cached_time_surf:
            self.cached_time_str = time_str
            self.cached_time_surf = self.font_huge.render(time_str, True, (255, 255, 255))
            self.cached_ampm_surf = self.font_med.render(ampm, True, TEXT_SECONDARY)

        if date_str != self.cached_date_str or not self.cached_date_surf:
            self.cached_date_str = date_str
            self.cached_date_surf = self.font_body.render(date_str, True, TEXT_SECONDARY)

        # 1. Left: Time, AM/PM, Date, Location
        x = self.pad_x
        y = self.pad_y
        self.screen.blit(self.cached_time_surf, (x, y))
        ampm_x = x + self.cached_time_surf.get_width() + int(10 * self.scale_x)
        ampm_y = y + self.cached_time_surf.get_height() - self.cached_ampm_surf.get_height() - int(6 * self.scale_y)
        self.screen.blit(self.cached_ampm_surf, (ampm_x, ampm_y))

        sub_y = y + self.cached_time_surf.get_height() + int(2 * self.scale_y)
        self.screen.blit(self.cached_date_surf, (x, sub_y))

        dot_surf = self.font_body.render(" • ", True, TEXT_MUTED)
        dot_x = x + self.cached_date_surf.get_width()
        self.screen.blit(dot_surf, (dot_x, sub_y))

        loc_text = (self.weather_data or {}).get("location", "Jacksonville, Florida")
        loc_surf = self.font_body.render(loc_text, True, (147, 197, 253))
        self.screen.blit(loc_surf, (dot_x + dot_surf.get_width(), sub_y))

        # 2. Right: Jarvis Helper Pill Widget (matching CSS .helper-card)
        pill_w = int(280 * self.scale_x)
        pill_h = int(58 * self.scale_y)
        pill_x = self.w - self.pad_x - pill_w
        pill_y = self.pad_y + int(4 * self.scale_y)

        state_color = STATE_COLORS.get(self.assistant_state, ACCENT_READY)
        state_label = STATE_LABELS.get(self.assistant_state, "READY")
        state_subtext = STATE_SUBTEXTS.get(self.assistant_state, 'Say "Hey Jarvis"')

        # Pill background
        pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
        self.draw_card(self.screen, pill_rect, bg=(20, 26, 38), border=state_color if self.assistant_state != "ready" else CARD_BORDER, radius=pill_h // 2, border_width=1.5 if self.assistant_state != "ready" else 1.0)

        # Pulsing Orb Icon in Pill
        orb_cx = pill_x + int(34 * self.scale_x)
        orb_cy = pill_y + pill_h // 2
        t = time.time()
        pulse = math.sin(t * 3.0) * (3.0 if self.assistant_state != "ready" else 1.5) * self.scale
        outer_r = max(8, int((14 + pulse) * self.scale))

        # Outer pulsing ring
        pygame.draw.circle(self.screen, (*state_color, 70), (orb_cx, orb_cy), outer_r, max(1, int(1.5 * self.scale)))
        # Inner solid dot
        pygame.draw.circle(self.screen, state_color, (orb_cx, orb_cy), max(4, int(7 * self.scale)))

        # Status text beside orb
        text_x = pill_x + int(60 * self.scale_x)
        badge_surf = self.font_small.render(state_label, True, state_color)
        subtext_surf = self.font_tiny.render(state_subtext, True, TEXT_MUTED)

        self.screen.blit(badge_surf, (text_x, pill_y + int(10 * self.scale_y)))
        self.screen.blit(subtext_surf, (text_x, pill_y + int(30 * self.scale_y)))

    def _render_hero_weather_surface(self):
        """Pre-renders the full-width current weather glass panel."""
        self.hero_surf.fill((0, 0, 0, 0))
        hero_rect = pygame.Rect(0, 0, self.hero_w, self.hero_h)
        self.draw_card(self.hero_surf, hero_rect, bg=CARD_BG, border=CARD_BORDER, radius=28)

        if not self.weather_data:
            loading_surf = self.font_large.render("Loading Live Forecast...", True, TEXT_MUTED)
            self.hero_surf.blit(loading_surf, (int(40 * self.scale_x), int(40 * self.scale_y)))
            return

        curr = self.weather_data.get("current", {})
        temp = curr.get("temp", "--")
        feels_like = curr.get("feels_like", "--")
        high = curr.get("high", "--")
        low = curr.get("low", "--")
        condition = curr.get("condition", "Clear Sky")
        humidity = curr.get("humidity", "--")
        wind_speed = curr.get("wind_speed", "--")
        rain_prob = curr.get("rain_prob", 0)
        uv_index = curr.get("uv_index", "--")

        # 1. Left Section: Weather Art Icon (Large 60px radius)
        art_cx = int(85 * self.scale_x)
        art_cy = int(120 * self.scale_y)
        self.draw_weather_symbol(self.hero_surf, condition, art_cx, art_cy, size=48)

        # 2. Huge Temperature Number
        temp_str = f"{temp}"
        temp_surf = self.font_giant.render(temp_str, True, (255, 255, 255))
        temp_x = int(165 * self.scale_x)
        temp_y = int(45 * self.scale_y)
        self.hero_surf.blit(temp_surf, (temp_x, temp_y))

        deg_surf = self.font_large.render("°", True, TEXT_SECONDARY)
        deg_x = temp_x + temp_surf.get_width() + int(2 * self.scale_x)
        deg_y = temp_y + int(12 * self.scale_y)
        self.hero_surf.blit(deg_surf, (deg_x, deg_y))

        # 3. Condition Title & Range Details
        detail_x = deg_x + int(45 * self.scale_x)
        cond_surf = self.font_large.render(str(condition), True, (255, 255, 255))
        self.hero_surf.blit(cond_surf, (detail_x, temp_y + int(10 * self.scale_y)))

        # Pill details: H: 87°  L: 74°  •  Feels like 96°
        pill_y = temp_y + cond_surf.get_height() + int(18 * self.scale_y)
        h_label = self.font_body.render(f"H: {high}°", True, TEMP_HOT)
        l_label = self.font_body.render(f"L: {low}°", True, TEMP_COOL)
        dot_label = self.font_body.render(" • ", True, TEXT_MUTED)
        f_label = self.font_body.render(f"Feels like {feels_like}°", True, TEXT_PRIMARY)

        hx = detail_x
        self.hero_surf.blit(h_label, (hx, pill_y))
        hx += h_label.get_width() + int(14 * self.scale_x)
        self.hero_surf.blit(l_label, (hx, pill_y))
        hx += l_label.get_width()
        self.hero_surf.blit(dot_label, (hx, pill_y))
        hx += dot_label.get_width()
        self.hero_surf.blit(f_label, (hx, pill_y))

        # 4. Right Section: 4 Metric Cards Grid (matching CSS .metrics-grid)
        metrics = [
            ("HUMIDITY", f"{humidity}%", (56, 189, 248)),
            ("WIND", f"{wind_speed} mph", (167, 139, 250)),
            ("RAIN PROB", f"{rain_prob}%", (96, 165, 250)),
            ("UV INDEX", f"{uv_index}", (251, 191, 36)),
        ]

        metric_w = int(180 * self.scale_x)
        metric_h = int(110 * self.scale_y)
        metric_gap = int(16 * self.scale_x)
        total_metrics_w = 4 * metric_w + 3 * metric_gap
        m_start_x = self.hero_w - total_metrics_w - int(40 * self.scale_x)
        m_y = int(85 * self.scale_y)

        for i, (label, val, accent_col) in enumerate(metrics):
            mx = m_start_x + i * (metric_w + metric_gap)
            m_rect = pygame.Rect(mx, m_y, metric_w, metric_h)
            self.draw_card(self.hero_surf, m_rect, bg=(26, 32, 48), border=CARD_BORDER, radius=18)

            lbl_surf = self.font_tiny.render(label, True, TEXT_MUTED)
            val_surf = self.font_med.render(val, True, (255, 255, 255))

            # Dot indicator with accent color
            pygame.draw.circle(self.hero_surf, accent_col, (mx + int(18 * self.scale_x), m_y + int(24 * self.scale_y)), max(3, int(4 * self.scale)))
            self.hero_surf.blit(lbl_surf, (mx + int(30 * self.scale_x), m_y + int(18 * self.scale_y)))
            self.hero_surf.blit(val_surf, (mx + int(18 * self.scale_x), m_y + int(52 * self.scale_y)))

    def _render_forecast_cards_surface(self):
        """Pre-renders 7 distinct horizontal daily forecast cards side-by-side."""
        self.forecast_surf.fill((0, 0, 0, 0))
        daily = (self.weather_data or {}).get("daily", [])
        if not daily:
            none_surf = self.font_body.render("Forecast loading...", True, TEXT_MUTED)
            self.forecast_surf.blit(none_surf, (int(20 * self.scale_x), int(40 * self.scale_y)))
            return

        num_cards = 7
        gap = int(14 * self.scale_x)
        card_w = int((self.hero_w - (num_cards - 1) * gap) / num_cards)
        card_h = self.forecast_cards_h

        for i in range(min(num_cards, len(daily))):
            day = daily[i]
            d_name = "Today" if i == 0 else str(day.get("short_name", day.get("day_name", f"Day {i}")))
            d_high = day.get("high", "--")
            d_low = day.get("low", "--")
            d_cond = str(day.get("condition", "Clear"))
            d_rain = day.get("rain_prob", 0)

            cx = i * (card_w + gap)
            c_rect = pygame.Rect(cx, 0, card_w, card_h)

            # Highlight 'Today' card with distinct border & brighter background
            is_today = (i == 0)
            c_bg = CARD_BG_TODAY if is_today else CARD_BG
            c_border = CARD_BORDER_TODAY if is_today else CARD_BORDER
            self.draw_card(self.forecast_surf, c_rect, bg=c_bg, border=c_border, radius=22, border_width=1.5 if is_today else 1.0)

            # 1. Day Title (Centered at top)
            day_col = (56, 189, 248) if is_today else TEXT_PRIMARY
            day_surf = self.font_med.render(d_name, True, day_col)
            self.forecast_surf.blit(day_surf, (cx + (card_w - day_surf.get_width()) // 2, int(26 * self.scale_y)))

            # 2. Weather Icon (Centered)
            icon_cy = int(card_h * 0.35)
            self.draw_weather_symbol(self.forecast_surf, d_cond, cx + card_w // 2, icon_cy, size=32)

            # 3. Short Condition Text (Centered)
            short_cond = d_cond.split("/")[0].strip()
            cond_surf = self.font_small.render(short_cond, True, TEXT_SECONDARY)
            cond_y = icon_cy + int(42 * self.scale_y)
            self.forecast_surf.blit(cond_surf, (cx + (card_w - cond_surf.get_width()) // 2, cond_y))

            # 4. Rain Probability Pill (Centered)
            rain_y = cond_y + int(36 * self.scale_y)
            if d_rain > 0:
                rain_str = f"Rain: {d_rain}%"
                rain_surf = self.font_small.render(rain_str, True, (96, 165, 250))
                self.forecast_surf.blit(rain_surf, (cx + (card_w - rain_surf.get_width()) // 2, rain_y))

            # 5. High / Low Temperatures (Centered at bottom)
            temp_y = card_h - int(65 * self.scale_y)
            hl_str = f"{d_high}° / {d_low}°"
            hl_surf = self.font_med.render(hl_str, True, TEXT_PRIMARY)
            self.forecast_surf.blit(hl_surf, (cx + (card_w - hl_surf.get_width()) // 2, temp_y))

    def draw_weather_and_forecast_section(self):
        """Blits pre-rendered Hero card and 7-day forecast cards."""
        if self.weather_dirty:
            self._render_hero_weather_surface()
            self._render_forecast_cards_surface()
            self.weather_dirty = False

        # Blit Hero Card
        self.screen.blit(self.hero_surf, (self.hero_x, self.hero_y))

        # Check if voice dialogue is active
        is_speech_active = (time.time() - self.last_speech_time < 12.0) and bool(self.transcription or self.assistant_reply)

        if is_speech_active:
            # Render Speech Dialogue Card over forecast section
            self.draw_speech_dialogue_overlay()
        else:
            # Render 7-Day Forecast Section Header & Cards
            title_surf = self.font_tiny.render("7-DAY FORECAST", True, TEXT_MUTED)
            self.screen.blit(title_surf, (self.hero_x + int(4 * self.scale_x), self.forecast_y))

            updated_surf = self.font_tiny.render("Updated just now", True, TEXT_MUTED)
            self.screen.blit(updated_surf, (self.hero_x + self.hero_w - updated_surf.get_width() - int(4 * self.scale_x), self.forecast_y))

            self.screen.blit(self.forecast_surf, (self.hero_x, self.forecast_cards_y))

    def draw_speech_dialogue_overlay(self):
        """Renders floating Glassmorphic Dialogue Card when user or assistant speaks."""
        card_rect = pygame.Rect(self.hero_x, self.forecast_cards_y, self.hero_w, self.forecast_cards_h)
        state_color = STATE_COLORS.get(self.assistant_state, ACCENT_READY)
        self.draw_card(self.screen, card_rect, bg=(16, 22, 35), border=state_color, radius=24, border_width=1.5)

        # Header bar
        header_y = self.forecast_cards_y + int(24 * self.scale_y)
        dot_x = self.hero_x + int(30 * self.scale_x)
        pygame.draw.circle(self.screen, state_color, (dot_x, header_y + int(10 * self.scale_y)), max(4, int(6 * self.scale)))

        title_surf = self.font_med.render("JARVIS ASSISTANT", True, (255, 255, 255))
        self.screen.blit(title_surf, (dot_x + int(18 * self.scale_x), header_y))

        div_y = header_y + title_surf.get_height() + int(16 * self.scale_y)
        pygame.draw.line(self.screen, CARD_BORDER, (self.hero_x + int(25 * self.scale_x), div_y), (self.hero_x + self.hero_w - int(25 * self.scale_x), div_y), max(1, int(1 * self.scale)))

        curr_y = div_y + int(20 * self.scale_y)
        dialogue_x = self.hero_x + int(35 * self.scale_x)
        max_w = self.hero_w - int(70 * self.scale_x)

        if self.transcription:
            u_label = self.font_small.render("YOU", True, ACCENT_LISTENING)
            self.screen.blit(u_label, (dialogue_x, curr_y))
            curr_y += u_label.get_height() + int(6 * self.scale_y)
            curr_y = self._render_wrapped_text(f'"{self.transcription}"', dialogue_x, curr_y, max_w, self.font_large, (255, 255, 255))
            curr_y += int(16 * self.scale_y)

        if self.assistant_reply:
            a_label = self.font_small.render("JARVIS", True, ACCENT_SPEAKING)
            self.screen.blit(a_label, (dialogue_x, curr_y))
            curr_y += a_label.get_height() + int(6 * self.scale_y)
            curr_y = self._render_wrapped_text(self.assistant_reply, dialogue_x, curr_y, max_w, self.font_large, (226, 232, 240))

    def _render_wrapped_text(self, text, x, y, max_width, font, color):
        """Safe word-wrap text renderer that avoids off-screen overflow."""
        clean_text = " ".join(str(text).replace("\r", " ").replace("\n", " ").split())
        words = clean_text.split(" ")
        lines = []
        curr_line = []

        for word in words:
            curr_line.append(word)
            test_str = " ".join(curr_line)
            w, _ = font.size(test_str)
            if w > max_width:
                curr_line.pop()
                lines.append(" ".join(curr_line))
                curr_line = [word]

        if curr_line:
            lines.append(" ".join(curr_line))

        for line in lines[:6]:
            try:
                s = font.render(line, True, color)
                self.screen.blit(s, (x, y))
                y += s.get_height() + max(2, int(6 * self.scale_y))
            except Exception:
                pass
        return y

    def run(self):
        """Ultra-smooth, low-CPU rendering loop clocked at 20 FPS."""
        def sig_handler(signum, frame):
            self.running = False

        signal.signal(signal.SIGTERM, sig_handler)
        signal.signal(signal.SIGINT, sig_handler)

        target_fps = 20.0
        frame_time = 1.0 / target_fps
        print(f"[DISPLAY] Native Glassmorphism Display started at {int(target_fps)} FPS...", flush=True)

        while self.running:
            start_t = time.perf_counter()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        self.running = False

            # Clear background
            self.screen.fill(BG_COLOR)

            if not self.screen_active:
                # Display is off: render a blank frame only (no UI work, low CPU)
                pygame.display.flip()
                elapsed = time.perf_counter() - start_t
                sleep_sec = frame_time - elapsed
                if sleep_sec > 0:
                    time.sleep(sleep_sec)
                continue

            # Draw UI components
            self.draw_header_section()
            self.draw_weather_and_forecast_section()

            # Flip buffer
            pygame.display.flip()

            elapsed = time.perf_counter() - start_t
            sleep_sec = frame_time - elapsed
            if sleep_sec > 0:
                time.sleep(sleep_sec)

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
