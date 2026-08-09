#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary="$(mktemp -d /tmp/winvm-smoke.XXXXXX)"
trap 'rm -rf -- "$temporary"' EXIT

scripts=(
    "$REPO_DIR/bin/winvm"
    "$REPO_DIR/bin/winui"
    "$REPO_DIR/scripts/common.sh"
    "$REPO_DIR/scripts/deploy-ui.sh"
    "$REPO_DIR/scripts/doctor.sh"
    "$REPO_DIR/scripts/generalize-windows.sh"
    "$REPO_DIR/scripts/image-factory.sh"
    "$REPO_DIR/scripts/image-manifest.sh"
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
[[ "$help_output" == *'factory-create NAME WINDOWS_ISO SEED_ISO'* ]]
[[ "$help_output" == *'generalize [--check|--decrypt|--confirm-target]'* ]]
[[ "$help_output" == *'generalize --remove-appx EXACT_PACKAGE_NAME'* ]]
[[ "$help_output" == *'export-image PATH'* ]]
[[ "$help_output" == *'image-manifest PATH [--oobe-confirmed]'* ]]
[[ "$help_output" == *'target-id'* ]]
[[ "$help_output" == *'pin-target ROLE'* ]]
[[ "$help_output" == *'assert-target OP'* ]]

config_output="$(
    WINVM_SSH_HOST=smoke-host \
    WINVM_PROVIDER=utm-macos \
    "$REPO_DIR/bin/winvm" ssh-config smoke-user
)"
[[ "$config_output" == *'Host smoke-host'* ]]
[[ "$config_output" == *'User smoke-user'* ]]
[[ "$config_output" == *'Port 22'* ]]
[[ "$config_output" == *'/providers/utm-macos/ssh-proxy %p'* ]]

printf "WINVM_UTM_NAME='configured-name'\n" > "$temporary/config"
{
    printf "WINVM_UTM_NAME='selected-name'\n"
    printf "WINVM_EXPECTED_UTM_ID='11111111-2222-3333-4444-555555555555'\n"
    printf "WINVM_TARGET_ROLE='candidate'\n"
} > "$temporary/target"
layered_names="$(
    WINVM_CONFIG_FILE="$temporary/config" \
    WINVM_TARGET_FILE="$temporary/target" \
    bash -c 'source "$1"; source "$1"; printf "%s|%s\n" "$WINVM_UTM_NAME" "$WINVM_CONFIGURED_UTM_NAME"' \
        _ "$REPO_DIR/scripts/common.sh"
)"
[[ "$layered_names" == 'selected-name|configured-name' ]]

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
[[ "$(jq -r '.lifecycle.export_image.kind' <<< "$blocked_json")" == 'utm_bundle' ]]
[[ "$(jq -r '.lifecycle.generalize.route' <<< "$blocked_json")" == 'guest_sysprep' ]]
[[ "$(jq -r '.image_factory.availability' <<< "$blocked_json")" == 'conditional' ]]
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

delete_capture="$temporary/delete-target"
delete_marker="$temporary/delete-complete"
env \
    WINVM_UTM_NAME='selected-name' \
    WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-delete-by-id" \
    WINVM_OSASCRIPT="$REPO_DIR/tests/fixtures/osascript-target-id" \
    WINVM_EXPECTED_UTM_ID=11111111-2222-3333-4444-555555555555 \
    WINVM_TARGET_ROLE=candidate \
    WINVM_TEST_DELETE_CAPTURE="$delete_capture" \
    WINVM_TEST_DELETE_MARKER="$delete_marker" \
    "$provider" delete --confirm selected-name >/dev/null
[[ "$(<"$delete_capture")" == '11111111-2222-3333-4444-555555555555' ]]

identity_provider_env=(
    WINVM_UTMCTL=/usr/bin/true
    WINVM_OSASCRIPT="$REPO_DIR/tests/fixtures/osascript-target-id"
    WINVM_EXPECTED_UTM_ID=11111111-2222-3333-4444-555555555555
)

assert_target() {
    env "${identity_provider_env[@]}" \
        WINVM_TARGET_ROLE="$1" \
        "$provider" assert-target "$2" "${3:-}"
}

candidate_json="$(assert_target candidate up --json)"
[[ "$(jq -r '.identity_pin' <<< "$candidate_json")" == 'verified' ]]
[[ "$(jq -r '.role' <<< "$candidate_json")" == 'candidate' ]]
[[ "$(jq -r '.operation' <<< "$candidate_json")" == 'up' ]]
[[ "$(jq -r '.authorized' <<< "$candidate_json")" == 'true' ]]
[[ "$(jq -r '.transport.ssh_alias' <<< "$candidate_json")" == 'winvm' ]]
assert_target candidate product-install >/dev/null
assert_target candidate generalize >/dev/null
assert_target candidate export-image >/dev/null
if assert_target seal product-install >/dev/null 2>&1; then
    printf 'Seal unexpectedly authorized persistent product installation.\n' >&2
    exit 1
fi

if env \
    WINVM_UTMCTL=/usr/bin/true \
    WINVM_OSASCRIPT="$REPO_DIR/tests/fixtures/osascript-target-id" \
    WINVM_TARGET_ROLE=candidate \
    "$provider" assert-target up >/dev/null 2>&1; then
    printf 'Unpinned target unexpectedly authorized mutation.\n' >&2
    exit 1
fi

if env \
    WINVM_UTMCTL=/usr/bin/true \
    WINVM_OSASCRIPT="$REPO_DIR/tests/fixtures/osascript-target-id" \
    WINVM_EXPECTED_UTM_ID=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee \
    WINVM_TARGET_ROLE=candidate \
    "$provider" assert-target up >/dev/null 2>&1; then
    printf 'Mismatched target identity unexpectedly authorized mutation.\n' >&2
    exit 1
fi

if assert_target source up >/dev/null 2>&1; then
    printf 'Source mutation unexpectedly succeeded without override.\n' >&2
    exit 1
fi
assert_target source seal >/dev/null
env "${identity_provider_env[@]}" \
    WINVM_TARGET_ROLE=source \
    WINVM_ALLOW_SOURCE_MUTATION=1 \
    "$provider" assert-target up >/dev/null
if assert_target source delete >/dev/null 2>&1; then
    printf 'Source delete unexpectedly passed role policy.\n' >&2
    exit 1
fi
if assert_target source generalize >/dev/null 2>&1; then
    printf 'Source generalization unexpectedly passed role policy.\n' >&2
    exit 1
fi

assert_target seal connect >/dev/null
assert_target seal disposable-up >/dev/null
assert_target seal seal >/dev/null
assert_target seal export-image >/dev/null
if assert_target seal up >/dev/null 2>&1; then
    printf 'Persistent seal boot unexpectedly succeeded without override.\n' >&2
    exit 1
fi
env "${identity_provider_env[@]}" \
    WINVM_TARGET_ROLE=seal \
    WINVM_ALLOW_PERSISTENT_SEAL_BOOT=1 \
    "$provider" assert-target up >/dev/null

if command -v swiftc >/dev/null 2>&1; then
    swiftc -typecheck "$REPO_DIR/providers/utm-macos/window-id.swift"
    swiftc -typecheck "$REPO_DIR/providers/utm-macos/normalize-screenshot.swift"
fi

printf 'Smoke tests passed.\n'
