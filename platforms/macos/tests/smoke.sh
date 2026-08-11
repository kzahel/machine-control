#!/usr/bin/env bash

set -euo pipefail

mode="${1:-}"
if [[ -n "$mode" && "$mode" != "--static" ]]; then
    printf 'Usage: tests/smoke.sh [--static]\n' >&2
    exit 2
fi

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary="$(mktemp -d /tmp/macvm-workspace-smoke.XXXXXX)"
trap 'rm -rf -- "$temporary"' EXIT
cd "$REPO_DIR"

for script in \
    bin/macui \
    bin/macvm \
    providers/tart-macos/provider.sh \
    providers/tart-macos/workspace.sh \
    providers/tart-macos/screenshot \
    scripts/common.sh \
    scripts/bootstrap-appliance.sh \
    scripts/candidate-status.sh \
    scripts/certify-appliance.sh \
    scripts/deploy-maintenance.sh \
    scripts/deploy-ui.sh \
    scripts/deploy-fixture.sh \
    scripts/deploy-admin-fixture.sh \
    scripts/deploy-privacy-fixture.sh \
    scripts/deploy-swiftui-fixture.sh \
    scripts/deploy-electron-fixture.sh \
    scripts/deploy-java-fixture.sh \
    scripts/framework-runtime-status.sh \
    scripts/install-framework-runtimes.sh \
    scripts/post-update.sh \
    scripts/reset-admin-fixture.sh \
    scripts/remove-fixture.sh \
    scripts/remove-admin-fixture.sh \
    scripts/reset-privacy-fixture.sh \
    scripts/remove-privacy-fixture.sh \
    scripts/remove-swiftui-fixture.sh \
    scripts/remove-electron-fixture.sh \
    scripts/remove-java-fixture.sh \
    scripts/submit-authorization.sh \
    scripts/fetch-artifact.sh \
    scripts/doctor-json.sh \
    scripts/doctor.sh \
    guests/macos/ui/machine-control \
    guests/macos/bootstrap/post-update.sh \
    guests/macos/bootstrap/bootstrap-guest.sh; do
    /bin/bash -n "$script"
done

/usr/bin/plutil -lint \
    guests/macos/bootstrap/org.cirruslabs.tart-guest-agent.plist.in \
    guests/macos/bootstrap/org.cirruslabs.tart-guest-daemon.plist.in \
    guests/macos/ui/com.kzahel.macvm-testbed.resident.plist.in \
    guests/macos/ui/Info.plist \
    guests/macos/fixture/Info.plist \
    guests/macos/admin-fixture/Info.plist \
    guests/macos/privacy-fixture/Info.plist \
    guests/macos/swiftui-fixture/Info.plist \
    >/dev/null

/usr/bin/swiftc -typecheck providers/tart-macos/host-control.swift
/usr/bin/swiftc -typecheck providers/tart-macos/normalize-screenshot.swift
/usr/bin/swiftc -typecheck -framework SystemConfiguration \
    guests/macos/ui/macui.swift
/usr/bin/swiftc -typecheck guests/macos/fixture/MachineControlFixture.swift
/usr/bin/swiftc -typecheck -framework AppKit \
    guests/macos/admin-fixture/AdminAuthorizationFixture.swift
/usr/bin/swiftc -typecheck -framework AppKit -framework ApplicationServices \
    -framework AVFoundation -framework Network -framework ScreenCaptureKit \
    -framework UserNotifications \
    guests/macos/privacy-fixture/PrivacyConsentFixture.swift
/usr/bin/swiftc -typecheck -parse-as-library -framework SwiftUI \
    guests/macos/swiftui-fixture/SwiftUIFixture.swift

/usr/bin/python3 -m json.tool \
    guests/macos/electron-fixture/package.json >/dev/null
for file in guests/macos/electron-fixture/main.js \
    guests/macos/electron-fixture/preload.js; do
    test -s "$file"
done
test -s guests/macos/java-fixture/MachineControlJavaFixture.java
source guests/macos/framework-runtimes/versions.env
[[ "$MACVM_NODE_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$MACVM_JAVA_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$MACVM_ELECTRON_SHA256" =~ ^[0-9a-f]{64}$ ]]

bin/macvm help >/dev/null
bin/macui help >/dev/null
help_output="$(bin/macvm help)"
[[ "$help_output" == *'post-update audit|repair'* ]]
[[ "$help_output" == *'appliance-certify'* ]]
[[ "$help_output" == *'bootstrap [--profile'* ]]
default_guard="$(env MACVM_CONFIG_FILE=/dev/null bash -c \
    'source "$1"; printf "%s|%s|%s" "$MACVM_REQUIRE_MUTATION_GUARD" "$MACVM_TARGET_ROLE" "$MACVM_EXPECTED_NAME"' \
    _ "$REPO_DIR/scripts/common.sh")"
[[ "$default_guard" == 'true|unspecified|' ]]
mutation_marker="$temporary/tart-mutated"
if env MACVM_CONFIG_FILE=/dev/null \
        MACVM_TART="$REPO_DIR/tests/fixtures/tart" \
        MACVM_NAME=fixture-default \
        MACHINE_CONTROL_TART_MUTATION_MARKER="$mutation_marker" \
        bin/macvm up >/dev/null 2>&1; then
    printf 'Default macOS configuration allowed a lifecycle mutation\n' >&2
    exit 1
fi
test ! -e "$mutation_marker"
workspace_caps="$(env \
    MACVM_CONFIG_FILE=/dev/null \
    MACVM_TART=/usr/bin/true \
    MACVM_NAME=fixture-development \
    MACVM_WORKSPACE_STATE_DIR="$temporary/capabilities" \
    MACVM_WORKSPACE_DEVELOPMENT_PROVEN=false \
    bin/macvm workspace-capabilities --json)"
jq -e '.schema == "machine-control-workspace-capabilities/v0" and
    .intents.persistent.availability == "unavailable"' \
    <<<"$workspace_caps" >/dev/null

workspace_handle="$(python3 "$REPO_DIR/../../providers/workspaces/receipts.py" \
    --state-dir "$temporary/selection" create \
    --provider tart-macos --intent isolated \
    --mechanism filesystem_cow_clone \
    --retention discardOnRelease --cleanup release --state running \
    --target-name fixture-workspace --target-id fixture-workspace \
    --source-name fixture-base --source-id fixture-base)"
selection="$({ env \
    MACVM_CONFIG_FILE=/dev/null \
    MACVM_WORKSPACE_STATE_DIR="$temporary/selection" \
    MACVM_SSH_HOST=fixture-fixed-endpoint \
    MACVM_WORKSPACE_GUEST_TRANSPORT=ssh \
    MACHINE_CONTROL_WORKSPACE_HANDLE="$workspace_handle" \
    bash -c 'source "$1"; printf "%s|%s|%s|%s|%s\n" "$MACVM_NAME" "$MACVM_EXPECTED_NAME" "$MACVM_TARGET_ROLE" "$MACVM_GUEST_TRANSPORT" "$MACVM_SSH_HOST"' \
        _ "$REPO_DIR/scripts/common.sh"; } 2>/dev/null)"
[[ "$selection" == \
    'fixture-workspace|fixture-workspace|disposable|ssh|' ]]
if MACVM_FORBID_OUTER_UI=true bin/macvm screenshot >/dev/null 2>&1; then
    printf 'Outer-UI guard allowed a Tart screenshot\n' >&2
    exit 1
fi
for command in click drag type key; do
    if MACVM_FORBID_OUTER_UI=true bin/macvm "$command" >/dev/null 2>&1; then
        printf 'Outer-UI guard allowed macvm %s\n' "$command" >&2
        exit 1
    fi
done

guest_home="$temporary/guest-home"
mkdir -p "$guest_home"
set +e
guest_audit="$(env -u BASH_ENV HOME="$guest_home" \
    guests/macos/bootstrap/post-update.sh --mode audit --profile runtime \
        --nonce abcdefghijklmnopqrstuvwx)"
guest_audit_status=$?
set -e
[[ "$guest_audit_status" -eq 1 ]]
jq -e '.schema == "machine-control-macos-post-update/v0" and
    .mode == "audit" and .profile == "runtime" and
    .nonce == "abcdefghijklmnopqrstuvwx" and .healthy == false and
    (.checks | length) == 11' <<<"$guest_audit" >/dev/null

maintenance="$REPO_DIR/tests/fixtures/macvm-maintenance"
doctor_ready="$REPO_DIR/tests/fixtures/doctor-ready"
maintenance_log="$temporary/maintenance.log"
maintenance_state="$temporary/maintenance.state"
maintenance_env=(
    env
    MACVM_CONFIG_FILE=/dev/null
    MACVM_REQUIRE_MUTATION_GUARD=false
    MACVM_TARGET_ROLE=candidate
    MACVM_BOOT_TIMEOUT=5
    MACHINE_CONTROL_MACVM_LOG="$maintenance_log"
    MACHINE_CONTROL_MACVM_STATE="$maintenance_state"
)

audit="$(${maintenance_env[@]} \
    MACVM_POST_UPDATE_MACVM="$maintenance" \
    MACVM_POST_UPDATE_DOCTOR="$doctor_ready" \
    "$REPO_DIR/scripts/post-update.sh" audit --json)"
jq -e '.healthy == true and .operation == "audit" and
    .route == "selected_guest_transport" and .reboot.observed == false' \
    <<<"$audit" >/dev/null
grep -q '^status ' "$maintenance_log"
! grep -q '^up ' "$maintenance_log"

: >"$maintenance_log"
printf 'stopped\n' >"$maintenance_state"
set +e
stopped_audit="$(${maintenance_env[@]} \
    MACVM_POST_UPDATE_MACVM="$maintenance" \
    MACVM_POST_UPDATE_DOCTOR="$doctor_ready" \
    "$REPO_DIR/scripts/post-update.sh" audit --json)"
stopped_status=$?
set -e
[[ "$stopped_status" -eq 1 ]]
jq -e '.failure == "target_not_running" and .healthy == false' \
    <<<"$stopped_audit" >/dev/null
[[ "$(wc -l <"$maintenance_log" | tr -d ' ')" -eq 1 ]]

: >"$maintenance_log"
rm -f -- "$maintenance_state.reboot"
repair="$(${maintenance_env[@]} \
    MACVM_POST_UPDATE_MACVM="$maintenance" \
    MACVM_POST_UPDATE_DOCTOR="$doctor_ready" \
    MACVM_POST_UPDATE_DEPLOY_UI=/usr/bin/true \
    MACVM_POST_UPDATE_DEPLOY_MAINTENANCE=/usr/bin/true \
    "$REPO_DIR/scripts/post-update.sh" repair --reboot --json)"
jq -e '.healthy == true and .operation == "repair" and
    .reboot == {requested:true,observed:true} and
    .post_update.mode == "audit"' <<<"$repair" >/dev/null
grep -q '^up ' "$maintenance_log"
grep -q '/sbin/shutdown -r now' "$maintenance_log"

: >"$maintenance_log"
set +e
bad_nonce="$(${maintenance_env[@]} \
    MACHINE_CONTROL_MACVM_BAD_NONCE=1 \
    MACVM_POST_UPDATE_MACVM="$maintenance" \
    MACVM_POST_UPDATE_DOCTOR="$doctor_ready" \
    "$REPO_DIR/scripts/post-update.sh" audit --json 2>/dev/null)"
bad_nonce_status=$?
set -e
[[ "$bad_nonce_status" -eq 1 ]]
jq -e '.failure == "guest_agent_or_support_unavailable"' \
    <<<"$bad_nonce" >/dev/null

: >"$maintenance_log"
bootstrap="$(${maintenance_env[@]} \
    MACVM_BOOTSTRAP_MACVM="$maintenance" \
    MACVM_BOOTSTRAP_DEPLOY_UI=/usr/bin/true \
    MACVM_BOOTSTRAP_DEPLOY_MAINTENANCE=/usr/bin/true \
    "$REPO_DIR/scripts/bootstrap-appliance.sh" --profile runtime --json)"
jq -e '.healthy == true and .profile == "runtime" and
    .profile_tools == "available"' <<<"$bootstrap" >/dev/null
grep -q '^exec /bin/bash -c ' "$maintenance_log"
grep -q '^post-update audit --profile runtime --json ' "$maintenance_log"

: >"$maintenance_log"
printf 'running\n' >"$maintenance_state"
rm -f -- "$maintenance_state.reboot"
if git -C "$REPO_DIR/../.." rev-parse --is-inside-work-tree \
        >/dev/null 2>&1; then
    certification="$(${maintenance_env[@]} \
        MACVM_CERTIFY_MACVM="$maintenance" \
        MACVM_CERTIFY_ALLOW_DIRTY_FOR_TESTS=1 \
        MACVM_CERTIFY_CHECK_TIMEOUT=60 \
        "$REPO_DIR/scripts/certify-appliance.sh" --json)"
    jq -e '.healthy == true and .final_power == "off" and
        .reboot.changedBootEpochObserved == true and
        .guest_checks.portable_checks == "passed" and
        .guest_checks.native_checks == "passed" and
        .guest_checks.staging_removed == true' <<<"$certification" >/dev/null
    grep -q '/sbin/shutdown -r now' "$maintenance_log"
    grep -q ' portable ' "$maintenance_log"
    grep -q ' native ' "$maintenance_log"
    grep -q '^shutdown ' "$maintenance_log"
    ! grep -Eq '(^| )(clone|workspace-|screenshot|click|type|key)( |$)' \
        "$maintenance_log"

    : >"$maintenance_log"
    printf 'running\n' >"$maintenance_state"
    rm -f -- "$maintenance_state.reboot"
    set +e
    failed_certification="$(${maintenance_env[@]} \
        MACHINE_CONTROL_MACVM_NATIVE_FAIL=1 \
        MACVM_CERTIFY_MACVM="$maintenance" \
        MACVM_CERTIFY_ALLOW_DIRTY_FOR_TESTS=1 \
        MACVM_CERTIFY_CHECK_TIMEOUT=60 \
        "$REPO_DIR/scripts/certify-appliance.sh" --json)"
    failed_certification_status=$?
    set -e
    [[ "$failed_certification_status" -eq 1 ]]
    jq -e '.healthy == false and .final_power == "running" and
        .guest_checks.failure == "native_checks_failed" and
        .guest_checks.staging_removed == true' \
        <<<"$failed_certification" >/dev/null
    ! grep -q '^shutdown ' "$maintenance_log"
    grep -q '/bin/rm -rf -- /private/tmp/machine-control-certify-' \
        "$maintenance_log"
fi

if ${maintenance_env[@]} \
        MACVM_CERTIFY_MACVM="$maintenance" \
        MACVM_CERTIFY_ALLOW_DIRTY_FOR_TESTS=1 \
        MACVM_CERTIFY_CHECK_TIMEOUT=59 \
        "$REPO_DIR/scripts/certify-appliance.sh" --json \
        >/dev/null 2>&1; then
    printf 'macOS certification accepted an invalid timeout\n' >&2
    exit 1
fi
if [[ "$mode" == "--static" ]]; then
    printf 'macOS native static checks passed\n'
    exit 0
fi
MACVM_FORBID_OUTER_UI=true bin/macvm status >/dev/null
bin/macvm doctor
bin/macvm doctor --json | /usr/bin/jq -e \
    '.schema == "machine-control-doctor/v0" and .ready == true' >/dev/null

artifact_dir="$REPO_DIR/.artifacts/smoke"
/bin/mkdir -p "$artifact_dir"
bin/macvm screenshot "$artifact_dir/guest.png" >/dev/null
bin/macvm exec /usr/bin/sw_vers >/dev/null
bin/macvm ui health | /usr/bin/jq -e 'has("accessibilityTrusted")' >/dev/null
bin/macvm ui apps >/dev/null
if bin/macvm ui health | /usr/bin/jq -e '.accessibilityTrusted == true' \
        >/dev/null; then
    bin/macvm ui windows --app Finder >/dev/null
    bin/macvm ui tree --app Finder --interactive --depth 6 --limit 100 \
        >/dev/null
fi
bin/macvm control '{"operation":"status"}' \
    | /usr/bin/jq -e '.accepted == true and .data.semanticState == "ready"' \
    >/dev/null

printf 'MacVM smoke test passed; screenshot: %s\n' "$artifact_dir/guest.png"
