#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly PYTHON="${PYTHON:-python3}"
temporary="$(mktemp -d /tmp/linuxvm-workspace-static.XXXXXX)"
trap 'rm -rf -- "$temporary"' EXIT

find "$REPO_DIR/bin" "$REPO_DIR/scripts" "$REPO_DIR/providers" \
    "$REPO_DIR/guests" "$REPO_DIR/tests" -type f \
    \( -name '*.sh' -o -perm -u+x \) -print0 | \
    xargs -0 file | awk -F: '/shell script/ { print $1 }' | \
    while IFS= read -r script; do bash -n "$script"; done

"$PYTHON" -m py_compile \
    "$REPO_DIR/guests/ubuntu/ui/linuxui.py" \
    "$REPO_DIR/guests/ubuntu/ui/linuxcontrol.py" \
    "$REPO_DIR/guests/ubuntu/input/linuxinputd.py" \
    "$REPO_DIR/guests/ubuntu/fixtures/control_fixture.py" \
    "$REPO_DIR/guests/ubuntu/fixtures/qt_fixture.py" \
    "$REPO_DIR/guests/ubuntu/fixtures/browser_fixture.py"

"$REPO_DIR/bin/linuxvm" help >/dev/null
default_guard="$(env LINUXVM_CONFIG_FILE=/dev/null bash -c \
    'source "$1"; printf "%s|%s|%s|%s" "$LINUXVM_REQUIRE_MUTATION_GUARD" "$LINUXVM_TARGET_ROLE" "$LINUXVM_EXPECTED_NAME" "$LINUXVM_EXPECTED_UUID"' \
    _ "$REPO_DIR/scripts/common.sh")"
[[ "$default_guard" == 'true|unspecified||' ]]
if [[ "$(uname -s)" == Darwin ]]; then
    mutation_marker="$temporary/utm-mutated"
    if env LINUXVM_CONFIG_FILE=/dev/null \
            LINUXVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl" \
            LINUXVM_UTM_NAME=fixture-default \
            MACHINE_CONTROL_UTM_MUTATION_MARKER="$mutation_marker" \
            "$REPO_DIR/bin/linuxvm" up >/dev/null 2>&1; then
        printf 'Default Linux configuration allowed a lifecycle mutation\n' >&2
        exit 1
    fi
    test ! -e "$mutation_marker"

    ip_race_counter="$temporary/ip-race-counter"
    ip_address="$(env \
        LINUXVM_CONFIG_FILE=/dev/null \
        LINUXVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl" \
        LINUXVM_UTM_NAME=fixture-default \
        LINUXVM_EXPECTED_NAME=fixture-default \
        LINUXVM_EXPECTED_UUID=fixture-id \
        LINUXVM_TARGET_ROLE=candidate \
        LINUXVM_BOOT_TIMEOUT=5 \
        MACHINE_CONTROL_UTM_IP_RACE_COUNTER="$ip_race_counter" \
        "$REPO_DIR/bin/linuxvm" ip)"
    [[ "$ip_address" == 192.0.2.10 ]]
    [[ "$(<"$ip_race_counter")" == 2 ]]
fi
if [[ "$(uname -s)" == Darwin ]]; then
    workspace_caps="$(env \
        LINUXVM_CONFIG_FILE=/dev/null \
        LINUXVM_UTMCTL=/usr/bin/true \
        LINUXVM_WORKSPACE_STATE_DIR="$temporary/capabilities" \
        LINUXVM_WORKSPACE_DEVELOPMENT_PROVEN=false \
        "$REPO_DIR/bin/linuxvm" workspace-capabilities --json)"
    jq -e '.schema == "machine-control-workspace-capabilities/v0" and
        .intents.persistent.availability == "unavailable"' \
        <<<"$workspace_caps" >/dev/null
fi

workspace_handle="$($PYTHON "$REPO_DIR/../../providers/workspaces/receipts.py" \
    --state-dir "$temporary/selection" create \
    --provider utm-macos-linux --intent isolated \
    --mechanism provider_disposable_overlay \
    --retention discardOnRelease --cleanup release --state running \
    --target-name fixture-workspace --target-id fixture-workspace-id \
    --source-name fixture-base --source-id fixture-base-id)"
selection="$({ env \
    LINUXVM_CONFIG_FILE=/dev/null \
    LINUXVM_WORKSPACE_STATE_DIR="$temporary/selection" \
    MACHINE_CONTROL_WORKSPACE_HANDLE="$workspace_handle" \
    bash -c 'source "$1"; printf "%s|%s|%s\n" "$LINUXVM_UTM_NAME" "$LINUXVM_EXPECTED_UUID" "$LINUXVM_TARGET_ROLE"' \
        _ "$REPO_DIR/scripts/common.sh"; } 2>/dev/null)"
[[ "$selection" == 'fixture-workspace|fixture-workspace-id|disposable' ]]
printf 'Linux native static checks passed\n'
