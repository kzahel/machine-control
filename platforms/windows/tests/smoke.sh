#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

scripts=(
    "$REPO_DIR/bin/winvm"
    "$REPO_DIR/bin/winui"
    "$REPO_DIR/scripts/common.sh"
    "$REPO_DIR/scripts/deploy-ui.sh"
    "$REPO_DIR/scripts/doctor.sh"
    "$REPO_DIR/providers/utm-macos/provider.sh"
    "$REPO_DIR/providers/utm-macos/screenshot"
    "$REPO_DIR/providers/utm-macos/ssh-proxy"
)

for script in "${scripts[@]}"; do
    bash -n "$script"
done

help_output="$(WINVM_UTM_NAME='Smoke Test VM' "$REPO_DIR/bin/winvm" help)"
[[ "$help_output" == *'stage-bootstrap'* ]]
[[ "$help_output" == *'deploy-ui'* ]]
[[ "$help_output" == *'capabilities'* ]]
[[ "$help_output" == *'down'* ]]
[[ "$help_output" == *'seal'* ]]
[[ "$help_output" == *'disposable-up'* ]]
[[ "$help_output" == *'delete --confirm NAME'* ]]

config_output="$(
    WINVM_SSH_HOST=smoke-host \
    WINVM_PROVIDER=utm-macos \
    "$REPO_DIR/bin/winvm" ssh-config smoke-user
)"
[[ "$config_output" == *'Host smoke-host'* ]]
[[ "$config_output" == *'User smoke-user'* ]]
[[ "$config_output" == *'Port 22'* ]]
[[ "$config_output" == *'/providers/utm-macos/ssh-proxy %p'* ]]

provider="$REPO_DIR/providers/utm-macos/provider.sh"
blocked_json="$(
    WINVM_UTMCTL=/usr/bin/true \
    WINVM_OSASCRIPT="$REPO_DIR/tests/fixtures/osascript-known-blockers" \
    WINVM_SUSPEND_POLICY=auto \
    "$provider" capabilities --json
)"
[[ "$(jq -r '.lifecycle.suspend.availability' <<< "$blocked_json")" == 'unavailable' ]]
[[ "$(jq -r '.lifecycle.default_down_action' <<< "$blocked_json")" == 'guest-shutdown' ]]
[[ "$(jq -r '.lifecycle.seal.availability' <<< "$blocked_json")" == 'available' ]]
[[ "$(jq -r '.lifecycle.disposable_start.persistence' <<< "$blocked_json")" == 'discard_on_stop' ]]
[[ "$(jq -r '.lifecycle.delete.requires | index("exact_name_confirmation") != null' <<< "$blocked_json")" == 'true' ]]
[[ "$(jq -r '.lifecycle.suspend.reasons | index("utm-qemu-gpu-display") != null' <<< "$blocked_json")" == 'true' ]]
[[ "$(jq -r '.lifecycle.suspend.reasons | index("utm-qemu-nvme-disk") != null' <<< "$blocked_json")" == 'true' ]]

enabled_json="$(
    WINVM_UTMCTL=/usr/bin/true \
    WINVM_SUSPEND_POLICY=enabled \
    "$provider" capabilities --json
)"
[[ "$(jq -r '.lifecycle.suspend.availability' <<< "$enabled_json")" == 'available' ]]
[[ "$(jq -r '.lifecycle.default_down_action' <<< "$enabled_json")" == 'suspend' ]]

unknown_json="$(
    WINVM_UTMCTL=/usr/bin/true \
    WINVM_OSASCRIPT=/usr/bin/false \
    WINVM_SUSPEND_POLICY=auto \
    "$provider" capabilities --json
)"
[[ "$(jq -r '.lifecycle.suspend.availability' <<< "$unknown_json")" == 'unknown' ]]
[[ "$(jq -r '.lifecycle.default_down_action' <<< "$unknown_json")" == 'guest-shutdown' ]]

if WINVM_UTMCTL=/usr/bin/true \
    WINVM_SUSPEND_POLICY=disabled \
    "$provider" suspend >/dev/null 2>&1; then
    printf 'Disabled suspend unexpectedly succeeded.\n' >&2
    exit 1
fi

if WINVM_UTM_NAME='same-name' \
    WINVM_UTMCTL=/usr/bin/true \
    "$provider" seal same-name >/dev/null 2>&1; then
    printf 'Same-name seal unexpectedly succeeded.\n' >&2
    exit 1
fi

if WINVM_UTM_NAME='configured-name' \
    WINVM_UTMCTL=/usr/bin/true \
    "$provider" delete --confirm wrong-name >/dev/null 2>&1; then
    printf 'Mismatched delete confirmation unexpectedly succeeded.\n' >&2
    exit 1
fi

if command -v swiftc >/dev/null 2>&1; then
    swiftc -typecheck "$REPO_DIR/providers/utm-macos/window-id.swift"
    swiftc -typecheck "$REPO_DIR/providers/utm-macos/normalize-screenshot.swift"
fi

printf 'Smoke tests passed.\n'
