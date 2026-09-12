#!/usr/bin/env bash
# Pi Google Home — Smart Display Kiosk Launcher
# Launches Cage (Wayland Kiosk Compositor) with Chromium in full-screen kiosk mode.

SERVER_URL="${1:-http://192.168.1.236:8765/display/}"
HEALTH_URL="http://192.168.1.236:8765/health"

echo "======================================================="
echo " Starting Pi Smart Display Kiosk..."
echo " Target: ${SERVER_URL}"
echo "======================================================="

# User runtime & seat environment
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

export LIBSEAT_BACKEND=seatd
export WLR_LIBINPUT_NO_DEVICES=1

# Wait up to 30 seconds for network and host server to be reachable on boot
echo "==> Verifying connection to host server at ${HEALTH_URL}..."
MAX_WAIT=30
while [ $MAX_WAIT -gt 0 ]; do
  if curl -s --connect-timeout 2 "${HEALTH_URL}" >/dev/null 2>&1; then
    echo "==> Host server is reachable!"
    break
  fi
  sleep 1
  MAX_WAIT=$((MAX_WAIT - 1))
done

# Launch Cage with Chromium in kiosk mode
exec cage -- chromium \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --ozone-platform=wayland \
  --enable-features=OverlayScrollbar \
  --renderer-process-limit=1 \
  --js-flags="--max-old-space-size=128" \
  --disable-dev-shm-usage \
  --check-for-update-interval=31536000 \
  --disable-pinch \
  --autoplay-policy=no-user-gesture-required \
  --disable-translate \
  --disable-session-crashed-bubble \
  "${SERVER_URL}"
