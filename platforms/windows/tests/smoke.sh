#!/usr/bin/env bash

set -euo pipefail

# This suite isolates legacy lifecycle behavior. Claim enforcement has its own
# cross-adapter suite under providers/claims/tests.
export MACHINE_CONTROL_CLAIM_POLICY=optional

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
grep -Fq 'sshd_config_default' \
    "$REPO_DIR/guests/windows/bootstrap-openssh.ps1"
grep -Fq "'System32\OpenSSH\ssh-keygen.exe'" \
    "$REPO_DIR/guests/windows/bootstrap-openssh.ps1"
grep -Fq "SecurityIdentifier]::new('S-1-5-18')" \
    "$REPO_DIR/guests/windows/bootstrap-openssh.ps1"
grep -Fq "Where-Object Name -Match '^ssh_host_.*_key$'" \
    "$REPO_DIR/guests/windows/bootstrap-openssh.ps1"
grep -Fq "'PowerShell\\7'" \
    "$REPO_DIR/guests/windows/bootstrap-openssh.ps1"
grep -Fq "PowerShell-\$powerShellVersion-win-arm64.zip" \
    "$REPO_DIR/guests/windows/bootstrap-openssh.ps1"
grep -Fq -- "-Name DefaultShellCommandOption" \
    "$REPO_DIR/guests/windows/bootstrap-openssh.ps1"
grep -Fq "'machine-control-windows-post-update/v0'" \
    "$REPO_DIR/guests/windows/post-update.ps1"
grep -Fq "'openssh_automation_shell'" \
    "$REPO_DIR/guests/windows/post-update.ps1"
grep -Fq "'Python.Python.3.13'" \
    "$REPO_DIR/guests/windows/bootstrap-development.ps1"
grep -Fq "'Microsoft.DotNet.SDK.8'" \
    "$REPO_DIR/guests/windows/bootstrap-development.ps1"
grep -Fq 'post-update.ps1' "$REPO_DIR/../../scripts/publish-windows.sh"
temporary="$(mktemp -d /tmp/winvm-smoke.XXXXXX)"
trap 'rm -rf -- "$temporary"' EXIT

scripts=(
    "$REPO_DIR/bin/winvm"
    "$REPO_DIR/bin/winui"
    "$REPO_DIR/scripts/common.sh"
    "$REPO_DIR/scripts/certify-appliance.sh"
    "$REPO_DIR/scripts/control.sh"
    "$REPO_DIR/scripts/deploy-ui.sh"
    "$REPO_DIR/scripts/doctor-json.sh"
    "$REPO_DIR/scripts/doctor.sh"
    "$REPO_DIR/scripts/fetch-artifact.sh"
    "$REPO_DIR/scripts/generalize-windows.sh"
    "$REPO_DIR/scripts/image-factory.sh"
    "$REPO_DIR/scripts/image-manifest.sh"
    "$REPO_DIR/scripts/post-update.sh"
    "$REPO_DIR/providers/utm-macos/provider.sh"
    "$REPO_DIR/providers/libvirt-linux/provider.sh"
    "$REPO_DIR/providers/utm-macos/workspace.sh"
    "$REPO_DIR/providers/utm-macos/screenshot"
    "$REPO_DIR/providers/utm-macos/ssh-proxy"
)

for script in "${scripts[@]}"; do
    bash -n "$script"
done

help_output="$(WINVM_UTM_NAME='Smoke Test VM' "$REPO_DIR/bin/winvm" help)"
[[ "$help_output" == *'stage-bootstrap'* ]]
[[ "$help_output" == *'deploy-ui'* ]]
[[ "$help_output" == *'doctor [--json]'* ]]
[[ "$help_output" == *'control-local JSON'* ]]
[[ "$help_output" == *'artifact ID [PATH]'* ]]
[[ "$help_output" == *'post-update audit|repair'* ]]
[[ "$help_output" == *'appliance-certify'* ]]
[[ "$help_output" == *'capabilities'* ]]
[[ "$help_output" == *'down'* ]]
[[ "$help_output" == *'seal'* ]]
[[ "$help_output" == *'disposable-up'* ]]
[[ "$help_output" == *'delete --confirm NAME'* ]]
[[ "$help_output" == *'factory-create NAME WINDOWS_ISO SEED_ISO [BOOT_IMAGE]'* ]]
[[ "$help_output" == *'factory-detach-installer'* ]]
[[ "$help_output" == *'factory-detach-media'* ]]
[[ "$help_output" == *'generalize [--check|--decrypt|--confirm-target]'* ]]
[[ "$help_output" == *'generalize --remove-appx EXACT_PACKAGE_NAME'* ]]
[[ "$help_output" == *'export-image PATH'* ]]
[[ "$help_output" == *'image-manifest PATH [--oobe-confirmed]'* ]]
[[ "$help_output" == *'target-id'* ]]
[[ "$help_output" == *'pin-target ROLE'* ]]
[[ "$help_output" == *'assert-target OP'* ]]
[[ "$help_output" == *'repair-registration'* ]]
[[ "$help_output" == *'workspace-capabilities'* ]]

workspace_caps="$(env \
    WINVM_CONFIG_FILE=/dev/null \
    WINVM_TARGET_FILE="$temporary/absent-target" \
    WINVM_UTMCTL=/usr/bin/true \
    WINVM_WORKSPACE_STATE_DIR="$temporary/windows-workspaces" \
    WINVM_WORKSPACE_DEVELOPMENT_PROVEN=false \
    "$REPO_DIR/bin/winvm" workspace-capabilities --json)"
jq -e '.schema == "machine-control-workspace-capabilities/v0" and
    .intents.persistent.availability == "unavailable" and
    .intents.candidate.availability == "unavailable"' \
    <<<"$workspace_caps" >/dev/null

workspace_handle="$(python3 "$REPO_DIR/../../providers/workspaces/receipts.py" \
    --state-dir "$temporary/windows-selection" create \
    --provider utm-macos-windows --intent isolated \
    --mechanism provider_disposable_overlay \
    --retention discardOnRelease --cleanup release --state running \
    --target-name fixture-workspace --target-id fixture-workspace-id \
    --source-name fixture-base --source-id fixture-base-id)"
selection="$({ env \
    WINVM_CONFIG_FILE=/dev/null \
    WINVM_TARGET_FILE="$temporary/absent-target" \
    WINVM_WORKSPACE_STATE_DIR="$temporary/windows-selection" \
    MACHINE_CONTROL_WORKSPACE_HANDLE="$workspace_handle" \
    bash -c 'source "$1"; printf "%s|%s|%s\n" "$WINVM_UTM_NAME" "$WINVM_EXPECTED_UTM_ID" "$WINVM_TARGET_ROLE"' \
        _ "$REPO_DIR/scripts/common.sh"; } 2>/dev/null)"
[[ "$selection" == 'fixture-workspace|fixture-workspace-id|seal' ]]

for command in screenshot type click key scan; do
    if WINVM_FORBID_OUTER_UI=true \
            WINVM_UTMCTL=/usr/bin/true \
            "$REPO_DIR/providers/utm-macos/provider.sh" "$command" \
            >/dev/null 2>&1; then
        printf 'Outer-UI guard allowed winvm %s\n' "$command" >&2
        exit 1
    fi
done

if "$REPO_DIR/scripts/control.sh" 'not-json' >/dev/null 2>&1; then
    printf 'Control wrapper accepted invalid JSON\n' >&2
    exit 1
fi
if "$REPO_DIR/scripts/fetch-artifact.sh" '../not-an-id' \
        >/dev/null 2>&1; then
    printf 'Artifact wrapper accepted an invalid identifier\n' >&2
    exit 1
fi

direct_ssh_capture="$temporary/direct-ssh-arguments"
direct_target_log="$temporary/direct-target-log"
direct_utmctl_log="$temporary/direct-utmctl-log"
direct_environment=(
    WINVM_CONFIG_FILE=/dev/null
    WINVM_TARGET_FILE="$temporary/absent-direct-target"
    WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-ssh-direct"
    WINVM_OSASCRIPT="$REPO_DIR/tests/fixtures/osascript-target-id"
    WINVM_SSH_BIN="$REPO_DIR/tests/fixtures/ssh-direct"
    WINVM_NC_BIN=/usr/bin/true
    WINVM_EXPECTED_UTM_ID=11111111-2222-3333-4444-555555555555
    WINVM_TARGET_ROLE=candidate
    WINVM_SSH_HOST=fixture-ssh-alias
    WINVM_TEST_DIRECT_SSH_CAPTURE="$direct_ssh_capture"
    WINVM_TEST_TARGET_ID_LOG="$direct_target_log"
    WINVM_TEST_DIRECT_UTMCTL_LOG="$direct_utmctl_log"
)

env "${direct_environment[@]}" \
    "$REPO_DIR/bin/winvm" ps 'exit 0' >/dev/null
direct_ssh_arguments="$(paste -sd '|' "$direct_ssh_capture")"
[[ "$direct_ssh_arguments" == \
    '-o|BatchMode=yes|-o|ProxyCommand=none|-o|HostName=192.0.2.10|-o|HostKeyAlias=fixture-ssh-alias|-o|CheckHostIP=no|-p|22|fixture-ssh-alias|exit 0' ]]
[[ "$(wc -l <"$direct_target_log" | tr -d ' ')" == 1 ]]
[[ "$(grep -c '^ip-address ' "$direct_utmctl_log")" == 1 ]]

rm -f -- "$direct_ssh_capture" "$direct_target_log" "$direct_utmctl_log"
if env "${direct_environment[@]}" \
        WINVM_EXPECTED_UTM_ID=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee \
        "$REPO_DIR/bin/winvm" ps 'exit 0' >/dev/null 2>&1; then
    printf 'Direct SSH accepted a mismatched exact target.\n' >&2
    exit 1
fi
[[ ! -e "$direct_ssh_capture" ]]

if env "${direct_environment[@]}" \
        WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-always-stopped" \
        WINVM_SSH_ALLOW_START=false \
        "$REPO_DIR/bin/winvm" ps 'exit 0' >/dev/null 2>&1; then
    printf 'Direct SSH started a target when start was prohibited.\n' >&2
    exit 1
fi
[[ ! -e "$direct_ssh_capture" ]]

rm -f -- "$direct_ssh_capture" "$direct_target_log" "$direct_utmctl_log"
direct_control="$(env "${direct_environment[@]}" \
    "$REPO_DIR/bin/winvm" control '{"operation":"status"}')"
[[ "$direct_control" == '{"fixture":"resident-call"}' ]]
[[ "$(wc -l <"$direct_target_log" | tr -d ' ')" == 1 ]]
[[ "$(grep -c '^ip-address ' "$direct_utmctl_log")" == 1 ]]

set +e
doctor_json="$(
    WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-always-stopped" \
    WINVM_FORBID_OUTER_UI=true \
    "$REPO_DIR/scripts/doctor-json.sh"
)"
doctor_exit=$?
set -e
[[ "$doctor_exit" -eq 1 ]]
jq -e '.schema == "machine-control-doctor/v0" and
    .ready == false and .states.power == "off" and
    .states.outer == "prohibited" and
    (.lifecycleOperations | index("suspend")) == null and
    .extensions.lifecycle.suspend.availability == "unknown" and
    .extensions.lifecycle.defaultDownAction == "guest-shutdown"' \
    <<<"$doctor_json" >/dev/null

config_output="$(
    WINVM_SSH_HOST=smoke-host \
    WINVM_PROVIDER=utm-macos \
    "$REPO_DIR/bin/winvm" ssh-config smoke-user
)"
[[ "$config_output" == *'Host smoke-host'* ]]
[[ "$config_output" == *'User smoke-user'* ]]
[[ "$config_output" == *'Port 22'* ]]
[[ "$config_output" == *'/providers/utm-macos/ssh-proxy %p'* ]]

doctor_environment=(
    WINVM_CONFIG_FILE=/dev/null
    WINVM_TARGET_FILE="$temporary/absent-doctor-target"
    WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-post-update"
    WINVM_EXPECTED_UTM_ID=11111111-2222-3333-4444-555555555555
    WINVM_TARGET_ROLE=candidate
    WINVM_OSASCRIPT="$REPO_DIR/tests/fixtures/osascript-target-id"
    WINVM_SSH_BIN="$REPO_DIR/tests/fixtures/ssh-doctor"
    WINVM_NC_BIN=/usr/bin/true
    WINVM_SUSPEND_POLICY=disabled
    WINVM_FORBID_OUTER_UI=true
)
doctor_ready="$(env "${doctor_environment[@]}" \
    "$REPO_DIR/scripts/doctor-json.sh")"
jq -e '.ready == true and .states.administration == "ready" and
    .states.desktop == "unlocked" and .states.resident == "ready" and
    .resident.generation == "fixture-generation" and
    .extensions.targetIdentity == "verified" and
    (.lifecycleOperations | index("suspend")) == null and
    .extensions.lifecycle.suspend.availability == "unavailable" and
    .extensions.lifecycle.suspend.reasons == ["configured-disabled"] and
    .extensions.lifecycle.defaultDownAction == "guest-shutdown" and
    any(.checks[]; .id == "identity" and .status == "pass")' \
    <<<"$doctor_ready" >/dev/null

set +e
doctor_unregistered="$(env \
    WINVM_CONFIG_FILE=/dev/null \
    WINVM_TARGET_FILE="$temporary/absent-unregistered-target" \
    WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-always-stopped" \
    WINVM_OSASCRIPT=/usr/bin/false \
    WINVM_EXPECTED_UTM_ID=11111111-2222-3333-4444-555555555555 \
    WINVM_TARGET_ROLE=candidate \
    "$REPO_DIR/scripts/doctor-json.sh")"
doctor_unregistered_exit=$?
set -e
[[ "$doctor_unregistered_exit" -eq 1 ]]
jq -e '.ready == false and .extensions.targetIdentity == "unavailable" and
    any(.checks[]; .id == "identity" and .status == "fail" and
        (.summary | contains("repair-registration before re-pinning")))' \
    <<<"$doctor_unregistered" >/dev/null

set +e
doctor_suspend_available="$(env \
    WINVM_CONFIG_FILE=/dev/null \
    WINVM_TARGET_FILE="$temporary/absent-suspend-target" \
    WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-always-stopped" \
    WINVM_SUSPEND_POLICY=enabled \
    "$REPO_DIR/scripts/doctor-json.sh")"
doctor_suspend_available_exit=$?
set -e
[[ "$doctor_suspend_available_exit" -eq 1 ]]
jq -e '(.lifecycleOperations | index("suspend")) != null and
    .extensions.lifecycle.suspend.availability == "available" and
    .extensions.lifecycle.defaultDownAction == "suspend"' \
    <<<"$doctor_suspend_available" >/dev/null

set +e
doctor_timeout="$(env "${doctor_environment[@]}" \
    WINVM_DOCTOR_GUEST_TIMEOUT=1 WINVM_TEST_DOCTOR_HANG=1 \
    "$REPO_DIR/scripts/doctor-json.sh")"
doctor_timeout_exit=$?
set -e
[[ "$doctor_timeout_exit" -eq 1 ]]
jq -e '.ready == false and .states.administration == "unavailable" and
    any(.checks[]; .id == "administration" and
        .summary == "Guest administration probe timed out")' \
    <<<"$doctor_timeout" >/dev/null

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
shutdown_environment=(
    WINVM_CONFIG_FILE=/dev/null
    WINVM_TARGET_FILE="$temporary/absent-shutdown-target"
    WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-shutdown"
    WINVM_OSASCRIPT="$REPO_DIR/tests/fixtures/osascript-target-id"
    WINVM_SSH_BIN="$REPO_DIR/tests/fixtures/ssh-shutdown"
    WINVM_EXPECTED_UTM_ID=11111111-2222-3333-4444-555555555555
    WINVM_TARGET_ROLE=candidate
    WINVM_GUEST_SHUTDOWN_GRACE=1
    WINVM_SHUTDOWN_TIMEOUT=1
    WINVM_TEST_SHUTDOWN_STATE="$temporary/shutdown-state"
    WINVM_TEST_SHUTDOWN_LOG="$temporary/shutdown-log"
)

rm -f -- "$temporary/shutdown-state" "$temporary/shutdown-log"
env "${shutdown_environment[@]}" WINVM_TEST_GUEST_SHUTDOWN_SUCCEEDS=1 \
    "$provider" shutdown >/dev/null
[[ "$(<"$temporary/shutdown-log")" == guest-shutdown ]]

rm -f -- "$temporary/shutdown-state" "$temporary/shutdown-log"
env "${shutdown_environment[@]}" WINVM_TEST_PROVIDER_SHUTDOWN_SUCCEEDS=1 \
    "$provider" shutdown >/dev/null
[[ "$(<"$temporary/shutdown-log")" == $'guest-shutdown\nprovider-request' ]]

rm -f -- "$temporary/shutdown-state" "$temporary/shutdown-log"
if env "${shutdown_environment[@]}" "$provider" shutdown \
        >/dev/null 2>&1; then
    printf 'Failed shutdown unexpectedly succeeded.\n' >&2
    exit 1
fi
[[ "$(<"$temporary/shutdown-log")" == $'guest-shutdown\nprovider-request' ]]

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
[[ "$(jq -r '.image_factory.requires | index("stopped_media_detachment") != null' <<< "$blocked_json")" == 'true' ]]
[[ "$(jq -r '.image_factory.requires | index("installer_detachment_before_bootstrap") != null' <<< "$blocked_json")" == 'true' ]]
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

mkdir -p "$temporary/factory-media"
touch "$temporary/factory-media/windows.iso" \
    "$temporary/factory-media/seed.iso" \
    "$temporary/factory-media/boot.img"
(
    cd "$temporary"
    factory_output="$(WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-factory-create" \
    WINVM_OSASCRIPT="$REPO_DIR/tests/fixtures/osascript-factory-create" \
    WINVM_TEST_FACTORY_UTMCTL_MARKER="$temporary/factory-created" \
    "$provider" factory-create fixture \
        factory-media/windows.iso factory-media/seed.iso \
        factory-media/boot.img)"
    [[ "$factory_output" == 'factory target created' ]]
)

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

registration_bundle="$temporary/selected-name.utm"
registration_marker="$temporary/registration-complete"
registration_capture="$temporary/registration-open-arguments"
mkdir -p "$registration_bundle"
touch "$registration_bundle/config.plist"
registration_output="$(env \
    WINVM_CONFIG_FILE=/dev/null \
    WINVM_TARGET_FILE="$temporary/absent-registration-target" \
    WINVM_UTM_NAME=selected-name \
    WINVM_UTM_BUNDLE="$registration_bundle" \
    WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-always-stopped" \
    WINVM_OSASCRIPT="$REPO_DIR/tests/fixtures/osascript-registration" \
    WINVM_OPEN="$REPO_DIR/tests/fixtures/open-registration" \
    WINVM_PLUTIL="$REPO_DIR/tests/fixtures/plutil-registration" \
    WINVM_EXPECTED_UTM_ID=11111111-2222-3333-4444-555555555555 \
    WINVM_TARGET_ROLE=candidate \
    WINVM_TEST_BUNDLE_ID=11111111-2222-3333-4444-555555555555 \
    WINVM_TEST_BUNDLE_NAME=selected-name \
    WINVM_TEST_REGISTRATION_MARKER="$registration_marker" \
    WINVM_TEST_OPEN_CAPTURE="$registration_capture" \
    "$provider" repair-registration)"
[[ "$registration_output" == \
    'target registration repaired: role=candidate state=stopped' ]]
[[ -f "$registration_marker" ]]
registration_arguments="$(paste -sd ' ' "$registration_capture")"
[[ "$registration_arguments" == "-g -a UTM $registration_bundle" ]]

rm -f -- "$registration_marker" "$registration_capture"
if env \
    WINVM_CONFIG_FILE=/dev/null \
    WINVM_TARGET_FILE="$temporary/absent-registration-target" \
    WINVM_UTM_NAME=selected-name \
    WINVM_UTM_BUNDLE="$registration_bundle" \
    WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-always-stopped" \
    WINVM_OSASCRIPT="$REPO_DIR/tests/fixtures/osascript-registration" \
    WINVM_OPEN="$REPO_DIR/tests/fixtures/open-registration" \
    WINVM_PLUTIL="$REPO_DIR/tests/fixtures/plutil-registration" \
    WINVM_EXPECTED_UTM_ID=11111111-2222-3333-4444-555555555555 \
    WINVM_TARGET_ROLE=candidate \
    WINVM_TEST_BUNDLE_ID=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee \
    WINVM_TEST_BUNDLE_NAME=selected-name \
    WINVM_TEST_REGISTRATION_MARKER="$registration_marker" \
    WINVM_TEST_OPEN_CAPTURE="$registration_capture" \
    "$provider" repair-registration >/dev/null 2>&1; then
    printf 'Registration repair accepted mismatched bundle identity.\n' >&2
    exit 1
fi
[[ ! -e "$registration_marker" && ! -e "$registration_capture" ]]

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
assert_target candidate post-update-repair >/dev/null
assert_target candidate appliance-certify >/dev/null
assert_target candidate generalize >/dev/null
assert_target candidate export-image >/dev/null
assert_target candidate factory-detach-installer >/dev/null
assert_target candidate factory-detach-media >/dev/null
if assert_target seal product-install >/dev/null 2>&1; then
    printf 'Seal unexpectedly authorized persistent product installation.\n' >&2
    exit 1
fi
if assert_target seal post-update-repair >/dev/null 2>&1; then
    printf 'Seal unexpectedly authorized post-update repair.\n' >&2
    exit 1
fi
if assert_target seal appliance-certify >/dev/null 2>&1; then
    printf 'Seal unexpectedly authorized appliance certification.\n' >&2
    exit 1
fi
if assert_target seal factory-detach-media >/dev/null 2>&1; then
    printf 'Seal unexpectedly authorized factory-media detachment.\n' >&2
    exit 1
fi

detach_installer_output="$(env \
    WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-always-stopped" \
    WINVM_OSASCRIPT="$REPO_DIR/tests/fixtures/osascript-factory-detach-installer" \
    WINVM_EXPECTED_UTM_ID=11111111-2222-3333-4444-555555555555 \
    WINVM_TARGET_ROLE=candidate \
    "$provider" factory-detach-installer)"
[[ "$detach_installer_output" == \
    'factory installer detached: removed=1 seed_media_remaining=2' ]]

detach_output="$(env \
    WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-always-stopped" \
    WINVM_OSASCRIPT="$REPO_DIR/tests/fixtures/osascript-factory-detach" \
    WINVM_EXPECTED_UTM_ID=11111111-2222-3333-4444-555555555555 \
    WINVM_TARGET_ROLE=candidate \
    "$provider" factory-detach-media)"
[[ "$detach_output" == 'factory media detached: removed=3 remaining=0' ]]

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

post_update_environment=(
    WINVM_CONFIG_FILE=/dev/null
    WINVM_TARGET_FILE="$temporary/absent-post-update-target"
    WINVM_OSASCRIPT="$REPO_DIR/tests/fixtures/osascript-target-id"
    WINVM_EXPECTED_UTM_ID=11111111-2222-3333-4444-555555555555
    WINVM_TARGET_ROLE=candidate
    WINVM_SSH_BIN="$REPO_DIR/tests/fixtures/ssh-post-update"
    WINVM_POST_UPDATE_DOCTOR="$REPO_DIR/tests/fixtures/doctor-ready"
    WINVM_TEST_SSH_READY_FILE="$temporary/post-update-ssh-ready"
    WINVM_TEST_QGA_REPORT_FILE="$temporary/post-update-qga-report"
)
touch "$temporary/post-update-ssh-ready"
post_update_audit="$(env "${post_update_environment[@]}" \
    WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-post-update" \
    "$REPO_DIR/bin/winvm" post-update audit --json)"
jq -e '.operation == "audit" and .route == "key_only_ssh" and
    .healthy == true and .reboot.requested == false and
    .post_update.mode == "audit" and .doctor.ready == true' \
    <<<"$post_update_audit" >/dev/null

rm -f -- "$temporary/post-update-ssh-ready" \
    "$temporary/post-update-qga-report"
post_update_repair="$(env "${post_update_environment[@]}" \
    WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-post-update" \
    "$REPO_DIR/bin/winvm" post-update repair --json)"
jq -e '.operation == "repair" and .route == "utm_guest_agent" and
    .healthy == true and .post_update.mode == "repair" and
    .doctor.ready == true' <<<"$post_update_repair" >/dev/null

rm -f -- "$temporary/post-update-qga-report"
if env "${post_update_environment[@]}" \
        WINVM_UTMCTL="$REPO_DIR/tests/fixtures/utmctl-post-update" \
        WINVM_POST_UPDATE_REPORT_TIMEOUT=1 \
        WINVM_TEST_QGA_WRONG_NONCE=1 \
        "$provider" post-update-guest-agent Development fixednonce \
        >/dev/null 2>&1; then
    printf 'Guest-agent repair accepted a mismatched report nonce.\n' >&2
    exit 1
fi

certify_environment=(
    WINVM_CERTIFY_ALLOW_DIRTY_FOR_TESTS=1
    WINVM_CERTIFY_WINVM="$REPO_DIR/tests/fixtures/winvm-certify"
    WINVM_SSH_BIN="$REPO_DIR/tests/fixtures/ssh-certify"
    WINVM_SCP_BIN="$REPO_DIR/tests/fixtures/scp-certify"
    WINVM_TEST_CERTIFY_REBOOT_FILE="$temporary/certify-rebooted"
    WINVM_TEST_CERTIFY_STOPPED_FILE="$temporary/certify-stopped"
)
certification="$(env "${certify_environment[@]}" \
    "$REPO_DIR/bin/winvm" appliance-certify --json)"
jq -e '.schema == "machine-control-windows-appliance-certification/v0" and
    .healthy == true and .reboot.observed == true and
    .guest_checks.portable_checks == "passed" and
    .guest_checks.native_checks == "passed" and .final_power == "off"' \
    <<<"$certification" >/dev/null
[[ -f "$temporary/certify-stopped" ]]

rm -f -- "$temporary/certify-rebooted" "$temporary/certify-stopped"
if env "${certify_environment[@]}" WINVM_TEST_CERTIFY_GUEST_FAIL=1 \
        "$REPO_DIR/bin/winvm" appliance-certify --json \
        >/dev/null 2>&1; then
    printf 'Appliance certification accepted failed guest checks.\n' >&2
    exit 1
fi
if [[ -f "$temporary/certify-stopped" ]]; then
    printf 'Failed appliance certification unexpectedly shut down the target.\n' >&2
    exit 1
fi
if env "${certify_environment[@]}" WINVM_CERTIFY_CHECK_TIMEOUT=invalid \
        "$REPO_DIR/bin/winvm" appliance-certify --json \
        >/dev/null 2>&1; then
    printf 'Appliance certification accepted an invalid check timeout.\n' >&2
    exit 1
fi

if env "${post_update_environment[@]}" \
        WINVM_UTMCTL=/usr/bin/true \
        "$REPO_DIR/bin/winvm" post-update audit --reboot \
        >/dev/null 2>&1; then
    printf 'Post-update audit unexpectedly accepted reboot.\n' >&2
    exit 1
fi
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

    raw_capture="$temporary/normalizer-raw.png"
    /usr/bin/swift - "$raw_capture" <<'SWIFT'
import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

let output = CommandLine.arguments[1]
let context = CGContext(
    data: nil,
    width: 20,
    height: 16,
    bitsPerComponent: 8,
    bytesPerRow: 0,
    space: CGColorSpaceCreateDeviceRGB(),
    bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
)!
context.setFillColor(CGColor(gray: 0.5, alpha: 1))
context.fill(CGRect(x: 0, y: 0, width: 20, height: 16))
let destination = CGImageDestinationCreateWithURL(
    URL(fileURLWithPath: output) as CFURL,
    UTType.png.identifier as CFString,
    1,
    nil
)!
CGImageDestinationAddImage(destination, context.makeImage()!, nil)
guard CGImageDestinationFinalize(destination) else { exit(1) }
SWIFT

    dynamic_capture="$temporary/normalizer-dynamic.png"
    /usr/bin/swift "$REPO_DIR/providers/utm-macos/normalize-screenshot.swift" \
        "$raw_capture" "$dynamic_capture" '' '' 10 8 1
    dynamic_size="$(sips -g pixelWidth -g pixelHeight "$dynamic_capture" |
        awk '/pixelWidth/{width=$2} /pixelHeight/{print width "x" $2}')"
    [[ "$dynamic_size" == 10x7 ]]

    fixed_capture="$temporary/normalizer-fixed.png"
    /usr/bin/swift "$REPO_DIR/providers/utm-macos/normalize-screenshot.swift" \
        "$raw_capture" "$fixed_capture" 14 9 10 8 1
    fixed_size="$(sips -g pixelWidth -g pixelHeight "$fixed_capture" |
        awk '/pixelWidth/{width=$2} /pixelHeight/{print width "x" $2}')"
    [[ "$fixed_size" == 14x9 ]]
fi

printf 'Smoke tests passed.\n'
