#!/usr/bin/env bash

set -uo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
failures=0

pass() {
    printf '[ok]   %s\n' "$*"
}

fail() {
    printf '[fail] %s\n' "$*" >&2
    failures=$((failures + 1))
}

warn() {
    printf '[warn] %s\n' "$*" >&2
}

printf 'vm=%s tart=%s guest-user=%s\n' \
    "$MACVM_NAME" "$MACVM_TART" "$MACVM_GUEST_USER"

if ! macvm_require_host; then
    exit 1
fi
if ! macvm_require_command jq; then
    exit 1
fi
pass "Tart $($MACVM_TART --version) on macOS"

if ! config_json="$(macvm_get_json 2>/dev/null)"; then
    fail "Tart VM does not exist: $MACVM_NAME"
    exit "$failures"
fi

state="$(printf '%s' "$config_json" | jq -r '.State // "unknown"')"
if [[ "$state" != "running" ]]; then
    fail "VM state is $state; run: $MACVM_REPO_DIR/bin/macvm up"
    exit "$failures"
fi
pass "VM state: $state"
pass "VM display: $(printf '%s' "$config_json" | jq -r '.Display')"

if [[ "$MACVM_FORBID_OUTER_UI" == "true" ]]; then
    pass 'outer UI is prohibited; host window capture/input is not required'
else
    host_control="$MACVM_REPO_DIR/providers/tart-macos/host-control.swift"
    if window_json="$(/usr/bin/swift "$host_control" window-info "$MACVM_NAME" 2>/dev/null)"; then
        pass "visible Tart window: id $(printf '%s' "$window_json" | jq -r '.id')"
    else
        fail 'no visible Tart window; screenshot and input require graphical tart run'
    fi

    if permissions="$(/usr/bin/swift "$host_control" permissions 2>/dev/null)"; then
        if [[ "$(printf '%s' "$permissions" | jq -r '.screenCapture')" == "true" ]]; then
            pass 'host Screen Recording access'
        else
            fail 'host Screen Recording access is missing'
        fi
        if [[ "$(printf '%s' "$permissions" | jq -r '.postEvent')" == "true" ]]; then
            pass 'host Accessibility input access'
        else
            fail 'host Accessibility input access is missing'
        fi
    else
        fail 'unable to inspect host capture/input permissions'
    fi
fi

if ! macvm_exec /usr/bin/true >/dev/null 2>&1; then
    fail "$MACVM_GUEST_TRANSPORT guest command channel is unavailable"
    exit "$failures"
fi
pass "$MACVM_GUEST_TRANSPORT guest command channel"

if ip="$(macvm_guest_ip 2>/dev/null)"; then
    pass "guest IPv4: $ip"
else
    fail 'guest IP resolution failed'
fi

guest_user="$(macvm_exec /usr/bin/stat -f %Su /dev/console 2>/dev/null || true)"
if [[ -n "$guest_user" && "$guest_user" != "root" && "$guest_user" != "loginwindow" ]]; then
    pass "interactive desktop user: $guest_user"
else
    fail 'no logged-in graphical desktop user'
fi

remote_binary="$(macvm_remote_ui_binary)"
if ! macvm_exec /bin/test -x "$remote_binary" \
        >/dev/null 2>&1; then
    fail "semantic UI helper is absent; run: $MACVM_REPO_DIR/bin/macvm deploy-ui"
else
    pass 'semantic UI helper is deployed'
    if health="$("$MACVM_REPO_DIR/bin/macui" health 2>/dev/null)" \
            && printf '%s' "$health" | jq -e . >/dev/null 2>&1; then
        if [[ "$(printf '%s' "$health" | jq -r '.accessibilityTrusted')" == "true" ]]; then
            pass 'guest Accessibility access'
        else
            warn "native helper Accessibility access is missing; run: $MACVM_REPO_DIR/bin/macvm authorize-ui"
        fi
        printf '%s\n' "$health" | jq .
    else
        fail 'semantic UI health query failed'
    fi
fi


if resident="$($MACVM_REPO_DIR/bin/macui control '{"operation":"capabilities"}' 2>/dev/null)" \
        && printf '%s' "$resident" | jq -e '.accepted == true' >/dev/null 2>&1; then
    ready_providers="$(printf '%s' "$resident" | jq \
        '[.data.providers[] | select(.state == "ready")] | length')"
    if (( ready_providers > 0 )); then
        pass "resident facade with $ready_providers ready provider(s)"
    else
        fail 'resident facade has no ready providers'
    fi
else
    fail 'resident facade is unavailable'
fi

if (( failures > 0 )); then
    printf '\n%s check(s) failed.\n' "$failures" >&2
    exit 1
fi

printf '\nAll macOS VM access checks passed.\n'
