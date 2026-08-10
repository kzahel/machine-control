#!/usr/bin/env bash

set -euo pipefail

if (( EUID != 0 )); then
    printf 'Run this script as root\n' >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
    qemu-guest-agent \
    spice-vdagent \
    python3-gi \
    gir1.2-atspi-2.0 \
    gnome-screenshot \
    python3-evdev \
    python3-pyqt5 \
    wl-clipboard \
    jq

# Ubuntu's qemu-guest-agent service is a static unit activated by the VirtIO
# guest-agent device, so enabling it directly is neither necessary nor valid.
systemctl start qemu-guest-agent
systemctl restart spice-vdagentd.service 2>/dev/null || true

systemctl is-active --quiet qemu-guest-agent
printf 'LinuxVM guest transport packages are ready.\n'
