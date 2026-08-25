#!/usr/bin/env bash

set -euo pipefail

if (( EUID != 0 )); then
    printf 'Run this script as root\n' >&2
    exit 1
fi

profile=runtime
nonce=""
report_path=""
while (( $# > 0 )); do
    case "$1" in
        --profile) profile="${2:-}"; shift 2 ;;
        --nonce) nonce="${2:-}"; shift 2 ;;
        --report-path) report_path="${2:-}"; shift 2 ;;
        *) printf 'Usage: bootstrap-guest.sh [--profile development|runtime] [--nonce NONCE --report-path PATH]\n' >&2; exit 2 ;;
    esac
done
if [[ "$profile" != development && "$profile" != runtime ]]; then
    printf 'Invalid bootstrap profile\n' >&2
    exit 2
fi
if [[ -n "$nonce" || -n "$report_path" ]]; then
    if [[ ! "$nonce" =~ ^[a-z0-9]{24}$ ||
          "$report_path" != "/var/tmp/machine-control-bootstrap-$nonce.json" ]]; then
        printf 'Invalid bootstrap report binding\n' >&2
        exit 2
    fi
fi

emit_report() {
    local healthy="$1" failure="$2" output
    output="$(jq -cn --arg profile "$profile" --arg nonce "$nonce" \
        --arg failure "$failure" --argjson healthy "$healthy" '{
            schema:"machine-control-linux-bootstrap/v0",
            healthy:$healthy,
            profile:$profile,
            nonce:(if $nonce == "" then null else $nonce end),
            guestAgent:(if $healthy then "active" else "unknown" end),
            packageProfile:(if $healthy then "installed" else "incomplete" end),
            failure:(if $failure == "" then null else $failure end)
        }')"
    if [[ -n "$report_path" ]]; then
        temporary_report="$report_path.$$"
        umask 077
        printf '%s\n' "$output" >"$temporary_report"
        mv -f -- "$temporary_report" "$report_path"
    else
        printf '%s\n' "$output"
    fi
}

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
        ! apt-get -o Dpkg::Options::=--force-confold install -y \
            "${packages[@]}" >>"$log" 2>&1; then
    emit_report false package_install_failed
    printf 'Ubuntu package profile installation failed\n' >&2
    exit 1
fi
if [[ "$profile" == development ]] &&
        ! snap list chromium >/dev/null 2>&1 &&
        ! snap install chromium >>"$log" 2>&1; then
    emit_report false browser_install_failed
    printf 'Ubuntu development browser installation failed\n' >&2
    exit 1
fi

# Ubuntu's qemu-guest-agent service is a static unit activated by the VirtIO
# guest-agent device, so enabling it directly is neither necessary nor valid.
systemctl start qemu-guest-agent
systemctl restart spice-vdagentd.service 2>/dev/null || true

if ! systemctl is-active --quiet qemu-guest-agent; then
    emit_report false guest_agent_inactive
    exit 1
fi
emit_report true ""
