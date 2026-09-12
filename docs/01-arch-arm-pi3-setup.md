# Step 01: Arch Linux ARM Installation on Raspberry Pi 3 Model B+

This guide documents the exact setup and provisioning procedure used to install and configure Arch Linux ARM (AArch64) on a Raspberry Pi 3 Model B+.

---

## 1. Hardware Architecture & Tarball Selection

- **Platform**: Raspberry Pi 3 Model B+ (Broadcom BCM2837B0, Quad-Core Cortex-A53 64-bit, 1GB LPDDR2 RAM).
- **Distribution**: Arch Linux ARM AArch64 (64-bit ARMv8).
- **Rootfs Image**: `ArchLinuxARM-rpi-aarch64-latest.tar.gz` from `http://os.archlinuxarm.org/os/`.
- **Rationale**: 64-bit instruction set is required for modern Python machine learning wheels (`openWakeWord`, ONNX Runtime, TFLite Runtime) which have dropped support for 32-bit `armv7h`.

---

## 2. Storage Partitioning Layout

The MicroSD card is partitioned using MBR (DOS partition table):

```
NAME     SIZE TYPE FSTYPE LABEL MOUNTPOINT
sda    119.3G disk              
├─sda1     1G part vfat   BOOT  /boot
└─sda2 118.3G part ext4   ROOT  /
```

- **Partition 1 (`/dev/sda1`)**: 1 GiB, Type `0x0c` (W95 FAT32 LBA), formatted with `mkfs.vfat`, labeled `BOOT`.
- **Partition 2 (`/dev/sda2`)**: Remainder (~118 GiB), Type `0x83` (Linux native), formatted with `mkfs.ext4`, labeled `ROOT`.

---

## 3. Rootfs Extraction & Bootloader Relocation

Extracted with `bsdtar` preserving root ownership, special device nodes, and setuid permissions:

```bash
bsdtar -xpf ArchLinuxARM-rpi-aarch64-latest.tar.gz -C /mnt/root
mv /mnt/root/boot/* /mnt/boot/
sync
```

Automated via [`scripts/install-alarm.sh`](../scripts/install-alarm.sh).

---

## 4. Boot Configuration (`/boot/config.txt`)

Added to the `BOOT` partition to support the 15" HDMI display and built-in speakers:

```ini
# Serial Console
enable_uart=1

# Audio Configuration
dtparam=audio=on

# Display & HDMI Audio Configuration (15" HDMI Monitor with built-in speakers)
hdmi_drive=2
hdmi_force_hotplug=1
disable_overscan=1

# GPU Memory allocation
gpu_mem=64
```

---

## 5. Wireless Pre-Configuration (`systemd-networkd` + `wpa_supplicant`)

Configured on the root partition prior to first boot:

- **`/etc/systemd/network/wlan.network`**:
  ```ini
  [Match]
  Name=wlan0

  [Network]
  DHCP=yes
  DNSSEC=no
  ```
- **`/etc/wpa_supplicant/wpa_supplicant-wlan0.conf`**: Generated using `wpa_passphrase` with `0600` permissions.
- **Service**: `wpa_supplicant@wlan0.service` enabled under `multi-user.target.wants`.

Automated via [`scripts/configure-wifi.sh`](../scripts/configure-wifi.sh).

---

## 6. Post-Boot Configuration on the Pi

1. Logged in via SSH (`alarm@<ip>`, default password `alarm`).
2. Switched to `root` (`su -`, default password `root`).
3. Ran full system update: `pacman -Syu`.
4. Installed `sudo`: `pacman -S sudo`.
5. Enabled `wheel` group for sudo: `echo "%wheel ALL=(ALL:ALL) ALL" > /etc/sudoers.d/wheel`.
6. Installed ALSA utilities and USB tools: `pacman -S alsa-utils usbutils`.
7. Added `alarm` to the `audio` group: `sudo usermod -aG audio alarm`.
