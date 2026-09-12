/**
 * Pi Google Home — Smart Display Client
 * Real-time clock, dynamic weather graphics, assistant state sync via WebSocket
 */

// SVG Weather Icons Generator
const WEATHER_SVGS = {
  "clear-day": `
    <svg viewBox="0 0 64 64" fill="none">
      <defs>
        <radialGradient id="sunGrad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#ffedd5"/>
          <stop offset="40%" stop-color="#f59e0b"/>
          <stop offset="100%" stop-color="#d97706"/>
        </radialGradient>
        <filter id="sunGlow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="3" result="blur"/>
          <feComposite in="SourceGraphic" in2="blur" operator="over"/>
        </filter>
      </defs>
      <circle cx="32" cy="32" r="14" fill="url(#sunGrad)" filter="url(#sunGlow)"/>
      <g stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" opacity="0.85">
        <line x1="32" y1="8" x2="32" y2="13"/>
        <line x1="32" y1="51" x2="32" y2="56"/>
        <line x1="8" y1="32" x2="13" y2="32"/>
        <line x1="51" y1="32" x2="56" y2="32"/>
        <line x1="15" y1="15" x2="19" y2="19"/>
        <line x1="45" y1="45" x2="49" y2="49"/>
        <line x1="15" y1="49" x2="19" y2="45"/>
        <line x1="45" y1="19" x2="49" y2="15"/>
      </g>
    </svg>
  `,
  "clear-night": `
    <svg viewBox="0 0 64 64" fill="none">
      <defs>
        <linearGradient id="moonGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#f1f5f9"/>
          <stop offset="100%" stop-color="#94a3b8"/>
        </linearGradient>
      </defs>
      <path d="M40 18C30.06 18 22 26.06 22 36C22 41.6 24.56 46.6 28.58 49.9C19.78 48.96 13 41.28 13 32C13 21.5 21.5 13 32 13C35.08 13 38 13.74 40.58 15.06C40.39 16.02 40 17 40 18Z" fill="url(#moonGrad)"/>
      <circle cx="48" cy="20" r="1.5" fill="#fef08a"/>
      <circle cx="44" cy="38" r="1.2" fill="#fef08a"/>
      <circle cx="52" cy="32" r="1" fill="#fef08a"/>
    </svg>
  `,
  "partly-cloudy-day": `
    <svg viewBox="0 0 64 64" fill="none">
      <defs>
        <radialGradient id="sunP" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#fef08a"/>
          <stop offset="100%" stop-color="#f59e0b"/>
        </radialGradient>
        <linearGradient id="cloudP" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="100%" stop-color="#94a3b8"/>
        </linearGradient>
      </defs>
      <circle cx="42" cy="24" r="11" fill="url(#sunP)"/>
      <path d="M44 48H20C14.48 48 10 43.52 10 38C10 32.8 13.98 28.52 19.04 28.06C20.88 21.84 26.68 17.34 33.48 17.34C41.44 17.34 48 23.36 48.74 31.06C52.88 31.78 56 35.38 56 39.7C56 44.28 52.28 48 47.7 48H44Z" fill="url(#cloudP)"/>
    </svg>
  `,
  "partly-cloudy-night": `
    <svg viewBox="0 0 64 64" fill="none">
      <defs>
        <linearGradient id="moonP" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#f8fafc"/>
          <stop offset="100%" stop-color="#cbd5e1"/>
        </linearGradient>
        <linearGradient id="cloudN" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#e2e8f0"/>
          <stop offset="100%" stop-color="#64748b"/>
        </linearGradient>
      </defs>
      <path d="M42 16C36 16 31.1 19.8 29.5 25.1C34.5 25.5 38.5 29.5 39 34.5C40.6 33.5 42 32 43 30C43 22.3 37 16 42 16Z" fill="url(#moonP)"/>
      <path d="M44 48H20C14.48 48 10 43.52 10 38C10 32.8 13.98 28.52 19.04 28.06C20.88 21.84 26.68 17.34 33.48 17.34C41.44 17.34 48 23.36 48.74 31.06C52.88 31.78 56 35.38 56 39.7C56 44.28 52.28 48 47.7 48H44Z" fill="url(#cloudN)"/>
    </svg>
  `,
  "cloudy": `
    <svg viewBox="0 0 64 64" fill="none">
      <defs>
        <linearGradient id="cloudDark" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#cbd5e1"/>
          <stop offset="100%" stop-color="#64748b"/>
        </linearGradient>
      </defs>
      <path d="M46 48H18C12.48 48 8 43.52 8 38C8 32.8 11.98 28.52 17.04 28.06C18.88 21.84 24.68 17.34 31.48 17.34C39.44 17.34 46 23.36 46.74 31.06C50.88 31.78 54 35.38 54 39.7C54 44.28 50.28 48 45.7 48H46Z" fill="url(#cloudDark)"/>
    </svg>
  `,
  "rain": `
    <svg viewBox="0 0 64 64" fill="none">
      <defs>
        <linearGradient id="cloudRain" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#94a3b8"/>
          <stop offset="100%" stop-color="#475569"/>
        </linearGradient>
      </defs>
      <path d="M44 42H18C13.58 42 10 38.42 10 34C10 29.84 13.18 26.42 17.23 26.05C18.7 21.07 23.34 17.5 28.78 17.5C35.15 17.5 40.4 22.32 41 28.48C44.31 29.06 46.8 31.94 46.8 35.4C46.8 39.06 43.82 42 40.16 42H44Z" fill="url(#cloudRain)"/>
      <line x1="20" y1="46" x2="16" y2="54" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round"/>
      <line x1="30" y1="46" x2="26" y2="54" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round"/>
      <line x1="40" y1="46" x2="36" y2="54" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round"/>
    </svg>
  `,
  "drizzle": `
    <svg viewBox="0 0 64 64" fill="none">
      <defs>
        <linearGradient id="cloudDrizzle" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#cbd5e1"/>
          <stop offset="100%" stop-color="#64748b"/>
        </linearGradient>
      </defs>
      <path d="M44 42H18C13.58 42 10 38.42 10 34C10 29.84 13.18 26.42 17.23 26.05C18.7 21.07 23.34 17.5 28.78 17.5C35.15 17.5 40.4 22.32 41 28.48C44.31 29.06 46.8 31.94 46.8 35.4C46.8 39.06 43.82 42 40.16 42H44Z" fill="url(#cloudDrizzle)"/>
      <circle cx="18" cy="49" r="1.5" fill="#38bdf8"/>
      <circle cx="28" cy="51" r="1.5" fill="#38bdf8"/>
      <circle cx="38" cy="49" r="1.5" fill="#38bdf8"/>
    </svg>
  `,
  "thunderstorm": `
    <svg viewBox="0 0 64 64" fill="none">
      <defs>
        <linearGradient id="cloudThunder" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#475569"/>
          <stop offset="100%" stop-color="#1e293b"/>
        </linearGradient>
      </defs>
      <path d="M44 38H18C13.58 38 10 34.42 10 30C10 25.84 13.18 22.42 17.23 22.05C18.7 17.07 23.34 13.5 28.78 13.5C35.15 13.5 40.4 18.32 41 24.48C44.31 25.06 46.8 27.94 46.8 31.4C46.8 35.06 43.82 38 40.16 38H44Z" fill="url(#cloudThunder)"/>
      <polygon points="30,36 24,46 31,46 27,56 38,44 32,44" fill="#facc15"/>
    </svg>
  `,
  "snow": `
    <svg viewBox="0 0 64 64" fill="none">
      <defs>
        <linearGradient id="cloudSnow" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#e2e8f0"/>
          <stop offset="100%" stop-color="#94a3b8"/>
        </linearGradient>
      </defs>
      <path d="M44 42H18C13.58 42 10 38.42 10 34C10 29.84 13.18 26.42 17.23 26.05C18.7 21.07 23.34 17.5 28.78 17.5C35.15 17.5 40.4 22.32 41 28.48C44.31 29.06 46.8 31.94 46.8 35.4C46.8 39.06 43.82 42 40.16 42H44Z" fill="url(#cloudSnow)"/>
      <circle cx="20" cy="50" r="2" fill="#ffffff"/>
      <circle cx="30" cy="49" r="2" fill="#ffffff"/>
      <circle cx="40" cy="51" r="2" fill="#ffffff"/>
    </svg>
  `,
  "fog": `
    <svg viewBox="0 0 64 64" fill="none">
      <line x1="14" y1="28" x2="50" y2="28" stroke="#94a3b8" stroke-width="3" stroke-linecap="round"/>
      <line x1="10" y1="36" x2="54" y2="36" stroke="#cbd5e1" stroke-width="3" stroke-linecap="round"/>
      <line x1="16" y1="44" x2="48" y2="44" stroke="#94a3b8" stroke-width="3" stroke-linecap="round"/>
    </svg>
  `
};

function getIconSvg(iconName) {
  return WEATHER_SVGS[iconName] || WEATHER_SVGS["partly-cloudy-day"];
}

// 1. Live Clock & Date Manager
function updateClock() {
  const now = new Date();
  let hours = now.getHours();
  const minutes = now.getMinutes();
  const ampm = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12;
  hours = hours ? hours : 12; // 0 hour is 12
  const formattedMinutes = minutes < 10 ? '0' + minutes : minutes;

  document.getElementById('clock-time').textContent = `${hours}:${formattedMinutes}`;
  document.getElementById('clock-ampm').textContent = ampm;

  const options = { weekday: 'long', month: 'long', day: 'numeric' };
  document.getElementById('clock-date').textContent = now.toLocaleDateString('en-US', options);
}

// 2. Weather Renderer
let lastWeatherData = null;

async function fetchWeather() {
  try {
    const res = await fetch('/api/weather');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.success) {
      lastWeatherData = data;
      renderWeather(data);
      const now = new Date();
      document.getElementById('last-updated').textContent = `Updated ${now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
    }
  } catch (err) {
    console.error('[WEATHER] Failed to load weather:', err);
  }
}

function renderWeather(data) {
  const { location, current, daily } = data;

  // Header location
  document.getElementById('header-location').textContent = location;

  // Hero section
  document.getElementById('current-weather-art').innerHTML = getIconSvg(current.icon);
  document.getElementById('current-temp').textContent = current.temp;
  document.getElementById('current-condition').textContent = current.condition;
  document.getElementById('current-high').textContent = `${current.high}°`;
  document.getElementById('current-low').textContent = `${current.low}°`;
  document.getElementById('current-feels').textContent = `${current.feels_like}°`;

  // Secondary metrics
  document.getElementById('metric-humidity').textContent = `${current.humidity}%`;
  document.getElementById('metric-wind').textContent = `${current.wind_speed} mph ${current.wind_direction}`;
  document.getElementById('metric-rain').textContent = `${current.rain_prob}%`;
  document.getElementById('metric-uv').textContent = `${current.uv_index}`;

  // 7-day forecast cards
  const container = document.getElementById('forecast-cards-container');
  container.innerHTML = '';

  // Calculate week min and max temp for the relative horizontal range bar
  let weekMin = 999;
  let weekMax = -999;
  daily.forEach(d => {
    if (d.low < weekMin) weekMin = d.low;
    if (d.high > weekMax) weekMax = d.high;
  });
  const tempSpan = Math.max(10, weekMax - weekMin);

  daily.slice(0, 7).forEach((day, index) => {
    const card = document.createElement('div');
    card.className = `forecast-day-card ${index === 0 ? 'today' : ''}`;

    const rainZero = day.rain_prob <= 0 ? 'zero' : '';

    // Relative percentage positions for bar fill
    const leftPct = Math.max(0, ((day.low - weekMin) / tempSpan) * 100);
    const widthPct = Math.max(15, ((day.high - day.low) / tempSpan) * 100);

    card.innerHTML = `
      <span class="f-day-name">${day.short_name}</span>
      <div class="f-icon-wrap">
        ${getIconSvg(day.icon)}
      </div>
      <div class="f-rain-badge ${rainZero}">
        <svg viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"></path>
        </svg>
        <span>${day.rain_prob}%</span>
      </div>
      <div class="f-temp-bar-wrap">
        <div class="f-temp-labels">
          <span class="f-low">${day.low}°</span>
          <span class="f-high">${day.high}°</span>
        </div>
        <div class="f-bar-track">
          <div class="f-bar-fill" style="margin-left: ${leftPct}%; width: ${widthPct}%;"></div>
        </div>
      </div>
    `;

    container.appendChild(card);
  });
}

// 3. Jarvis Assistant State Manager
const STATE_CONFIG = {
  "ready": {
    className: "state-ready",
    label: "READY",
    subtext: 'Say "Hey Jarvis"'
  },
  "idle": {
    className: "state-ready",
    label: "READY",
    subtext: 'Say "Hey Jarvis"'
  },
  "listening": {
    className: "state-listening",
    label: "LISTENING",
    subtext: "Listening to query..."
  },
  "thinking": {
    className: "state-querying",
    label: "QUERYING",
    subtext: "Processing answer..."
  },
  "querying": {
    className: "state-querying",
    label: "QUERYING",
    subtext: "Processing answer..."
  },
  "speaking": {
    className: "state-speaking",
    label: "SPEAKING",
    subtext: "Jarvis speaking"
  }
};

let overlayDismissTimeout = null;

function setAssistantState(stateName) {
  const cleanState = (stateName || "ready").toLowerCase();
  const conf = STATE_CONFIG[cleanState] || STATE_CONFIG["ready"];

  const widget = document.getElementById('helper-widget');
  widget.className = `helper-card ${conf.className}`;
  document.getElementById('helper-state-label').textContent = conf.label;
  document.getElementById('helper-subtext').textContent = conf.subtext;

  // Manage speech overlay
  const overlay = document.getElementById('assistant-overlay');
  const userBubble = document.getElementById('user-speech-bubble');
  const assistantBubble = document.getElementById('assistant-speech-bubble');

  if (cleanState === 'listening') {
    clearTimeout(overlayDismissTimeout);
    document.getElementById('user-speech-text').textContent = "Listening...";
    document.getElementById('assistant-speech-text').textContent = "";
    userBubble.classList.remove('hidden');
    assistantBubble.classList.add('hidden');
    overlay.classList.remove('hidden');
  } else if (cleanState === 'thinking' || cleanState === 'querying') {
    clearTimeout(overlayDismissTimeout);
    if (!document.getElementById('assistant-speech-text').textContent) {
      document.getElementById('assistant-speech-text').textContent = "Thinking...";
      assistantBubble.classList.remove('hidden');
    }
    overlay.classList.remove('hidden');
  } else if (cleanState === 'speaking') {
    clearTimeout(overlayDismissTimeout);
    overlay.classList.remove('hidden');
  } else if (cleanState === 'ready' || cleanState === 'idle') {
    // Graceful auto-fade back to ambient weather after speaking turn finishes
    clearTimeout(overlayDismissTimeout);
    overlayDismissTimeout = setTimeout(() => {
      overlay.classList.add('hidden');
      setTimeout(() => {
        document.getElementById('user-speech-text').textContent = "";
        document.getElementById('assistant-speech-text').textContent = "";
        userBubble.classList.add('hidden');
        assistantBubble.classList.add('hidden');
      }, 400);
    }, 5000);
  }
}

function setTranscription(text) {
  if (!text) return;
  document.getElementById('user-speech-text').textContent = text;
  document.getElementById('user-speech-bubble').classList.remove('hidden');
}

function setAssistantReply(text) {
  if (!text) return;
  document.getElementById('assistant-speech-text').textContent = text;
  document.getElementById('assistant-speech-bubble').classList.remove('hidden');
}

// 4. Real-Time Display WebSocket Client
let ws = null;
let reconnectTimer = null;
let heartbeatTimer = null;

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const wsUrl = `${protocol}//${host}/ws/display`;

  console.log(`[WS] Connecting to Display Stream: ${wsUrl}`);
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log('[WS] Connected to Display Gateway');
    clearTimeout(reconnectTimer);
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    heartbeatTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 5000);
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'pong') return;
      handleGatewayEvent(data);
    } catch (e) {
      console.warn('[WS] Non-JSON payload received:', event.data);
    }
  };

  ws.onclose = () => {
    console.warn('[WS] Disconnected from server. Reconnecting in 3s...');
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = (err) => {
    console.error('[WS] Connection error:', err);
    ws.close();
  };
}

function handleGatewayEvent(msg) {
  const type = msg.type;
  const payload = msg.payload || {};

  switch (type) {
    case 'state_change':
      setAssistantState(payload.state);
      break;
    case 'transcription':
      setTranscription(payload.text);
      break;
    case 'assistant_reply':
      setAssistantReply(payload.text);
      break;
    case 'weather_update':
      if (payload.weather) {
        renderWeather(payload.weather);
      } else {
        fetchWeather();
      }
      break;
    default:
      break;
  }
}

// Initialization on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  updateClock();
  setInterval(updateClock, 1000);

  fetchWeather();
  setInterval(fetchWeather, 15 * 60 * 1000); // 15 mins

  connectWebSocket();
});
