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

config_output="$(
    WINVM_SSH_HOST=smoke-host \
    WINVM_PROVIDER=utm-macos \
    "$REPO_DIR/bin/winvm" ssh-config smoke-user
)"
[[ "$config_output" == *'Host smoke-host'* ]]
[[ "$config_output" == *'User smoke-user'* ]]
[[ "$config_output" == *'Port 22'* ]]
[[ "$config_output" == *'/providers/utm-macos/ssh-proxy %p'* ]]

if command -v swiftc >/dev/null 2>&1; then
    swiftc -typecheck "$REPO_DIR/providers/utm-macos/window-id.swift"
fi

printf 'Smoke tests passed.\n'
