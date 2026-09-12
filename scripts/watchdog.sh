#!/usr/bin/env bash
# Pi Google Home — System Watchdog & Auto-Recovery Supervisor
# Continuously monitors the Smart Display Kiosk and Voice Assistant daemon.
# Automatically restarts any failed or dead processes.

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"

CHECK_INTERVAL=10

echo "======================================================="
echo " Pi Google Home Watchdog Supervisor Online"
echo " Monitoring services every ${CHECK_INTERVAL}s..."
echo "======================================================="

while true; do
  # 1. Check Voice Assistant Client
  if ! systemctl --user is-active --quiet assistant-client; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WATCHDOG] assistant-client is NOT active! Restarting..."
    systemctl --user restart assistant-client
  else
    # Verify that python client/main.py process is actually alive
    if ! pgrep -f "client/main.py" >/dev/null 2>&1; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WATCHDOG] main.py process missing! Restarting assistant-client..."
      systemctl --user restart assistant-client
    fi
  fi

  # 2. Check Smart Display Kiosk
  if ! systemctl --user is-active --quiet smart-display; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WATCHDOG] smart-display is NOT active! Restarting..."
    systemctl --user restart smart-display
  else
    # Verify that pygame_display.py, cage, or start_kiosk.sh process is alive
    if ! (pgrep -f "pygame_display.py" >/dev/null 2>&1 || pgrep -f "cage" >/dev/null 2>&1 || pgrep -f "start_kiosk.sh" >/dev/null 2>&1); then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WATCHDOG] display process missing! Restarting smart-display..."
      systemctl --user restart smart-display
    fi
  fi

  sleep "${CHECK_INTERVAL}"
done
