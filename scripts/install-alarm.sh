#!/usr/bin/env bash
set -euo pipefail

# Pi Google Home — Arch Linux ARM SD Card Provisioning Script
# Targets: /dev/sda1 (BOOT, FAT32) & /dev/sda2 (ROOT, ext4)

TARBALL="/home/todd/Downloads/ArchLinuxARM-rpi-aarch64-latest.tar.gz"
BOOT_DEV="/dev/sda1"
ROOT_DEV="/dev/sda2"

if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] This script must be run as root (use sudo)." >&2
    exit 1
fi

if [ ! -f "$TARBALL" ]; then
    echo "[ERROR] Tarball not found: $TARBALL" >&2
    exit 1
fi

if [ ! -b "$BOOT_DEV" ] || [ ! -b "$ROOT_DEV" ]; then
    echo "[ERROR] Expected block devices $BOOT_DEV and $ROOT_DEV not found." >&2
    exit 1
fi

echo "==> Target block devices verified:"
lsblk -o NAME,SIZE,TYPE,FSTYPE,LABEL "$BOOT_DEV" "$ROOT_DEV"

# Create clean temporary mount points
TMP_DIR=$(mktemp -d /tmp/alarm-install.XXXXXX)
BOOT_MNT="$TMP_DIR/boot"
ROOT_MNT="$TMP_DIR/root"
mkdir -p "$BOOT_MNT" "$ROOT_MNT"

cleanup() {
    echo "==> Cleaning up mountpoints..."
    sync || true
    if mountpoint -q "$BOOT_MNT"; then umount "$BOOT_MNT" || true; fi
    if mountpoint -q "$ROOT_MNT"; then umount "$ROOT_MNT" || true; fi
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM

echo "==> Mounting partitions..."
mount "$BOOT_DEV" "$BOOT_MNT"
mount "$ROOT_DEV" "$ROOT_MNT"

echo "==> Extracting rootfs to $ROOT_DEV (this will take ~1-2 minutes)..."
bsdtar -xpf "$TARBALL" -C "$ROOT_MNT"

echo "==> Moving bootloader & kernel files to $BOOT_DEV..."
mv "$ROOT_MNT"/boot/* "$BOOT_MNT"/

echo "==> Syncing filesystems to disk..."
sync

echo "==> Unmounting..."
umount "$BOOT_MNT"
umount "$ROOT_MNT"
rm -rf "$TMP_DIR"
trap - EXIT INT TERM

echo "============================================================"
echo " [SUCCESS] Arch Linux ARM successfully installed onto /dev/sda!"
echo " Both partitions have been safely unmounted."
echo "============================================================"
