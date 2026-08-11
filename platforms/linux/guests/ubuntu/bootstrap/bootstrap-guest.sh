#!/usr/bin/env bash

set -euo pipefail

if (( EUID != 0 )); then
    printf 'Run this script as root\n' >&2
    exit 1
fi

profile=runtime
if [[ "${1:-}" == --profile && $# -eq 2 ]]; then
    profile="$2"
elif (( $# != 0 )); then
    printf 'Usage: bootstrap-guest.sh [--profile development|runtime]\n' >&2
    exit 2
fi
if [[ "$profile" != development && "$profile" != runtime ]]; then
    printf 'Usage: bootstrap-guest.sh [--profile development|runtime]\n' >&2
    exit 2
fi

export DEBIAN_FRONTEND=noninteractive
packages=(
    qemu-guest-agent
    spice-vdagent
    python3-gi
    gir1.2-atspi-2.0
    gnome-screenshot
    python3-evdev
    python3-pyqt5
    wl-clipboard
    jq
)
if [[ "$profile" == development ]]; then
    packages+=(git build-essential python3-venv)
fi

log="$(mktemp /var/tmp/machine-control-bootstrap.XXXXXX.log)"
trap 'rm -f -- "$log"' EXIT
if ! apt-get update >"$log" 2>&1 ||
        ! apt-get install -y "${packages[@]}" >>"$log" 2>&1; then
    printf 'Ubuntu package profile installation failed; inspect the target-local apt log\n' >&2
    exit 1
fi

# Ubuntu's qemu-guest-agent service is a static unit activated by the VirtIO
# guest-agent device, so enabling it directly is neither necessary nor valid.
systemctl start qemu-guest-agent
systemctl restart spice-vdagentd.service 2>/dev/null || true

systemctl is-active --quiet qemu-guest-agent
jq -cn --arg profile "$profile" '{
    schema:"machine-control-linux-bootstrap/v0",
    healthy:true,
    profile:$profile,
    guestAgent:"active",
    packageProfile:"installed"
}'
