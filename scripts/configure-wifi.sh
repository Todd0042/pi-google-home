#!/usr/bin/env bash
set -euo pipefail

# Pi Google Home — Wi-Fi Pre-Configuration Script for Arch Linux ARM
# Configures wpa_supplicant and systemd-networkd on /dev/sda2 (ROOT)

ROOT_DEV="/dev/sda2"
COUNTRY="${COUNTRY:-US}"

if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] This script must be run as root (use sudo)." >&2
    exit 1
fi

if [ ! -b "$ROOT_DEV" ]; then
    echo "[ERROR] Block device $ROOT_DEV not found." >&2
    exit 1
fi

SSID="${1:-}"
PASS="${2:-}"

if [ -z "$SSID" ]; then
    read -rp "Enter Wi-Fi SSID (Network Name): " SSID
fi

if [ -z "$PASS" ]; then
    read -rsp "Enter Wi-Fi Password: " PASS
    echo
fi

TMP_MNT=$(mktemp -d /tmp/alarm-wifi.XXXXXX)
cleanup() {
    sync || true
    if mountpoint -q "$TMP_MNT"; then umount "$TMP_MNT" || true; fi
    rm -rf "$TMP_MNT"
}
trap cleanup EXIT INT TERM

echo "==> Mounting $ROOT_DEV to $TMP_MNT..."
mount "$ROOT_DEV" "$TMP_MNT"

echo "==> Configuring systemd-networkd for wlan0..."
cat <<EOF > "$TMP_MNT/etc/systemd/network/wlan.network"
[Match]
Name=wlan0

[Network]
DHCP=yes
DNSSEC=no
EOF

echo "==> Generating wpa_supplicant-wlan0.conf..."
mkdir -p "$TMP_MNT/etc/wpa_supplicant"
cat <<EOF > "$TMP_MNT/etc/wpa_supplicant/wpa_supplicant-wlan0.conf"
ctrl_interface=/var/run/wpa_supplicant
update_config=1
country=$COUNTRY

EOF

# Append network credentials block
wpa_passphrase "$SSID" "$PASS" >> "$TMP_MNT/etc/wpa_supplicant/wpa_supplicant-wlan0.conf"
chmod 600 "$TMP_MNT/etc/wpa_supplicant/wpa_supplicant-wlan0.conf"

echo "==> Enabling wpa_supplicant@wlan0.service..."
mkdir -p "$TMP_MNT/etc/systemd/system/multi-user.target.wants"
ln -sf /usr/lib/systemd/system/wpa_supplicant@.service \
    "$TMP_MNT/etc/systemd/system/multi-user.target.wants/wpa_supplicant@wlan0.service"

echo "==> Syncing and unmounting..."
sync
umount "$TMP_MNT"
rm -rf "$TMP_MNT"
trap - EXIT INT TERM

echo "============================================================"
echo " [SUCCESS] Wi-Fi configured for SSID '$SSID' on wlan0!"
echo " The Pi will automatically connect to Wi-Fi on boot."
echo "============================================================"
