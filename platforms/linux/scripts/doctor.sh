#!/usr/bin/env bash

set -uo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly LINUXVM="$LINUXVM_REPO_DIR/bin/linuxvm"
readonly PROVIDER="$(linuxvm_provider_path)"

failures=0

ok() { printf '[ok]   %s\n' "$1"; }
bad() { printf '[fail] %s\n' "$1"; failures=$((failures + 1)); }

if [[ "$(uname -s)" == "Darwin" && -x "$LINUXVM_UTMCTL" ]]; then
    ok "UTM $("$LINUXVM_UTMCTL" version) on macOS"
else
    bad "UTM CLI on macOS"
fi

status="$($PROVIDER status 2>/dev/null || true)"
[[ "$status" == "started" ]] && ok "VM state: started" || bad "VM state: $status"

permissions="$($PROVIDER permissions 2>/dev/null || true)"
if [[ "$(jq -r '.screenCapture // false' <<<"$permissions" 2>/dev/null)" == "true" ]]; then
    ok "host Screen Recording access"
else
    bad "host Screen Recording access"
fi
if [[ "$(jq -r '.postEvent // false' <<<"$permissions" 2>/dev/null)" == "true" ]]; then
    ok "host Accessibility input access"
else
    bad "host Accessibility input access"
fi

if $PROVIDER window-info >/dev/null 2>&1; then
    ok "visible UTM window"
else
    bad "visible UTM window"
fi

if $PROVIDER exec /usr/bin/id >/dev/null 2>&1; then
    ok "QEMU guest-agent command channel"
else
    bad "QEMU guest-agent command channel"
fi

ip="$($PROVIDER ip 2>/dev/null || true)"
[[ -n "$ip" ]] && ok "guest IPv4: $ip" || bad "guest IPv4"

user="$($LINUXVM desktop-user 2>/dev/null || true)"
[[ -n "$user" ]] && ok "active desktop user: $user" || bad "active desktop user"

session_type="$($PROVIDER exec /usr/bin/bash -lc \
    'pid=$(pgrep -n -x gnome-shell); tr "\0" "\n" < "/proc/$pid/environ" | sed -n "s/^XDG_SESSION_TYPE=//p"' \
    2>/dev/null || true)"
[[ "$session_type" == "wayland" ]] && ok "GNOME Wayland session" || bad "Wayland session: $session_type"

if $PROVIDER exec /usr/bin/systemctl is-active --quiet qemu-guest-agent; then
    ok "qemu-guest-agent service"
else
    bad "qemu-guest-agent service"
fi
if $PROVIDER exec /usr/bin/pgrep -x spice-vdagent >/dev/null 2>&1; then
    ok "interactive SPICE agent"
else
    bad "interactive SPICE agent"
fi

if $PROVIDER exec /usr/bin/test -x "$LINUXVM_UI_REMOTE"; then
    ok "semantic UI helper deployed"
else
    bad "semantic UI helper deployed"
fi
if ui_health="$($LINUXVM ui health 2>/dev/null)" && \
   [[ "$(jq -r '.atspiAvailable // false' <<<"$ui_health")" == "true" ]]; then
    ok "AT-SPI desktop access"
    printf '%s\n' "$ui_health"
else
    bad "AT-SPI desktop access"
fi

if (( failures > 0 )); then
    printf '\n%d LinuxVM access check(s) failed.\n' "$failures" >&2
    exit 1
fi
printf '\nAll Ubuntu VM access checks passed.\n'
