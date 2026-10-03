#!/usr/bin/env bash

set -euo pipefail
trap 'printf "macOS smoke failed at line %s: %s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR

# This suite isolates Tart and resident-control behavior. Claim enforcement is
# covered by the shared cross-adapter claim suite.
export MACHINE_CONTROL_CLAIM_POLICY=optional

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
    bin/machost \
    providers/tart-macos/provider.sh \
    providers/tart-macos/workspace.sh \
    providers/tart-macos/screenshot \
    scripts/common.sh \
    scripts/bootstrap-appliance.sh \
    scripts/candidate-status.sh \
    scripts/certify-appliance.sh \
    scripts/deploy-maintenance.sh \
    scripts/deploy-ui.sh \
    scripts/grant-resident-consent.sh \
    scripts/unlock-provider.sh \
    guests/macos/unlock/build.sh \
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
    resident/scripts/build-app.sh \
    resident/scripts/install-user.sh \
    resident/scripts/install-policy.sh \
    resident/scripts/install-browser.sh \
    guests/macos/bootstrap/post-update.sh \
    guests/macos/bootstrap/bootstrap-guest.sh; do
    /bin/bash -n "$script"
done

/usr/bin/plutil -lint \
    guests/macos/bootstrap/org.cirruslabs.tart-guest-agent.plist.in \
    guests/macos/bootstrap/org.cirruslabs.tart-guest-daemon.plist.in \
    resident/app/Info.plist \
    resident/app/org.machine-control.resident.plist.in \
    guests/macos/fixture/Info.plist \
    guests/macos/admin-fixture/Info.plist \
    guests/macos/privacy-fixture/Info.plist \
    guests/macos/swiftui-fixture/Info.plist \
    >/dev/null

/usr/bin/swiftc -typecheck providers/tart-macos/host-control.swift
/usr/bin/swiftc -typecheck tests/fixtures/outer-keyboard.swift
/usr/bin/swiftc -typecheck providers/tart-macos/normalize-screenshot.swift
/usr/bin/swiftc -typecheck -framework SystemConfiguration \
    resident/Sources/macui/*.swift
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
/usr/bin/python3 -m py_compile host/machost.py
bin/machost help >/dev/null
# The unpacked extension's fixed key must produce the ID that the native
# host registration allows.
/usr/bin/python3 - ../../providers/chrome-extension/manifest.json \
    resident/scripts/install-browser.sh <<'PY'
import base64, hashlib, json, re, sys
key = json.load(open(sys.argv[1]))["key"]
digest = hashlib.sha256(base64.b64decode(key)).hexdigest()[:32]
derived = "".join(chr(ord("a") + int(c, 16)) for c in digest)
script = open(sys.argv[2]).read()
assert f"DEFAULT_EXTENSION_ID='{derived}'" in script, derived
PY
if command -v node >/dev/null 2>&1; then
    node --check ../../providers/chrome-extension/service_worker.js
fi
for policy in resident/policies/*.json; do
    /usr/bin/python3 -m json.tool "$policy" >/dev/null
done
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
printf 'MACVM_ADMIN_SECRET_FILE=%q\n' "$temporary/config-secret" \
    >"$temporary/override.conf"
secret_override="$(env MACVM_CONFIG_FILE="$temporary/override.conf" \
    MACVM_ADMIN_SECRET_FILE="$temporary/environment-secret" \
    bash -c 'source "$1"; printf "%s" "$MACVM_ADMIN_SECRET_FILE"' \
    _ "$REPO_DIR/scripts/common.sh")"
[[ "$secret_override" == "$temporary/environment-secret" ]]
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
tart_ip="$(env \
    MACVM_CONFIG_FILE=/dev/null \
    MACVM_TART="$REPO_DIR/tests/fixtures/tart" \
    MACVM_NAME=fixture-development \
    MACVM_GUEST_TRANSPORT=tart \
    MACVM_SSH_HOST=198.51.100.5 \
    bash -c 'source "$1"; macvm_guest_ip' \
        _ "$REPO_DIR/scripts/common.sh")"
[[ "$tart_ip" == '192.0.2.1' ]]
ssh_fixed_ip="$(env \
    MACVM_CONFIG_FILE=/dev/null \
    MACVM_TART="$REPO_DIR/tests/fixtures/tart" \
    MACVM_NAME=fixture-development \
    MACVM_GUEST_TRANSPORT=ssh \
    MACVM_SSH_HOST=198.51.100.5 \
    bash -c 'source "$1"; macvm_guest_ip' \
        _ "$REPO_DIR/scripts/common.sh")"
[[ "$ssh_fixed_ip" == '198.51.100.5' ]]
ssh_discovered_ip="$(env \
    MACVM_CONFIG_FILE=/dev/null \
    MACVM_TART="$REPO_DIR/tests/fixtures/tart" \
    MACVM_NAME=fixture-development \
    MACVM_GUEST_TRANSPORT=ssh \
    bash -c 'source "$1"; macvm_guest_ip' \
        _ "$REPO_DIR/scripts/common.sh")"
[[ "$ssh_discovered_ip" == '192.0.2.1' ]]
if env \
        MACVM_CONFIG_FILE=/dev/null \
        MACVM_TART="$REPO_DIR/tests/fixtures/tart" \
        MACVM_NAME=fixture-development \
        MACVM_GUEST_TRANSPORT=invalid \
        bash -c 'source "$1"; macvm_guest_ip' \
            _ "$REPO_DIR/scripts/common.sh" >/dev/null 2>&1; then
    printf 'Unsupported macOS guest transport resolved an IP address\n' >&2
    exit 1
fi
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

secret_probe="$temporary/secret-probe"
secret_env=(
    env MACVM_CONFIG_FILE=/dev/null
    MACVM_NAME=fixture-candidate MACVM_EXPECTED_NAME=fixture-candidate
    MACVM_TARGET_ROLE=candidate MACVM_REQUIRE_MUTATION_GUARD=true
    MACVM_TART="$REPO_DIR/tests/fixtures/tart"
    MACVM_IOREG="$REPO_DIR/tests/fixtures/ioreg"
    MACHINE_CONTROL_HOST_SESSION=unlocked
    MACHINE_CONTROL_HOST_ATTENDANCE=unattended
)
if "${secret_env[@]}" MACVM_ADMIN_SECRET_FILE="$temporary/missing" \
        providers/tart-macos/provider.sh type-secret >"$secret_probe" 2>&1; then
    printf 'Missing guest secret reached outer input\n' >&2
    exit 1
fi
grep -q 'owner-only guest credential file' "$secret_probe"
printf 'fixture-only\n' >"$temporary/insecure-secret"
chmod 0644 "$temporary/insecure-secret"
if "${secret_env[@]}" MACVM_ADMIN_SECRET_FILE="$temporary/insecure-secret" \
        providers/tart-macos/provider.sh type-secret >"$secret_probe" 2>&1; then
    printf 'Insecure guest secret reached outer input\n' >&2
    exit 1
fi
grep -q 'owner-only guest credential file' "$secret_probe"

for host_case in locked:locked unlocked:unlocked background:not_on_console \
        none:no_session broken:unknown; do
    host_state="$(env MACVM_CONFIG_FILE=/dev/null \
        MACVM_IOREG="$REPO_DIR/tests/fixtures/ioreg" \
        MACHINE_CONTROL_HOST_SESSION="${host_case%%:*}" \
        bash -c 'source "$1"; macvm_host_session_state' \
            _ "$REPO_DIR/scripts/common.sh")"
    [[ "$host_state" == "${host_case#*:}" ]]
done
attendance_home="$temporary/attendance-config"
mkdir -p "$attendance_home/machine-control"
for attendance_case in env:unattended:unattended file:attended:attended \
        file:sometimes:invalid none::unspecified; do
    IFS=: read -r attendance_source attendance_value attendance_expected \
        <<<"$attendance_case"
    rm -f "$attendance_home/machine-control/config.json"
    attendance_env=()
    case "$attendance_source" in
        env) attendance_env=(MACHINE_CONTROL_HOST_ATTENDANCE="$attendance_value") ;;
        file)
            printf '{"schema":"machine-control-controller/v0","hostAttendance":"%s"}\n' \
                "$attendance_value" >"$attendance_home/machine-control/config.json"
            ;;
    esac
    attendance="$(env -u MACHINE_CONTROL_HOST_ATTENDANCE \
        MACVM_CONFIG_FILE=/dev/null XDG_CONFIG_HOME="$attendance_home" \
        ${attendance_env[@]+"${attendance_env[@]}"} \
        bash -c 'source "$1"; macvm_host_attendance' \
            _ "$REPO_DIR/scripts/common.sh")"
    [[ "$attendance" == "$attendance_expected" ]]
done
for input_case in unattended:locked:'host session is locked' \
        attended:unlocked:'declared attended'; do
    IFS=: read -r attendance host_session reason <<<"$input_case"
    set +e
    refusal="$(env MACVM_CONFIG_FILE=/dev/null MACVM_FORBID_OUTER_UI=false \
        MACVM_IOREG="$REPO_DIR/tests/fixtures/ioreg" \
        MACVM_TART="$REPO_DIR/tests/fixtures/tart" \
        MACHINE_CONTROL_HOST_ATTENDANCE="$attendance" \
        MACHINE_CONTROL_HOST_SESSION="$host_session" \
        providers/tart-macos/provider.sh click 10 10 2>&1)"
    refusal_status=$?
    set -e
    [[ "$refusal_status" -ne 0 && "$refusal" == *"$reason"* ]]
done
lifecycle_env=(
    env
    MACVM_CONFIG_FILE=/dev/null
    MACVM_TART="$REPO_DIR/tests/fixtures/tart"
    MACVM_IOREG="$REPO_DIR/tests/fixtures/ioreg"
    MACVM_NAME=fixture-lifecycle
    MACVM_EXPECTED_NAME=fixture-lifecycle
    MACVM_TARGET_ROLE=disposable
    MACHINE_CONTROL_TART_MUTATION_MARKER="$mutation_marker"
)
for suspend_case in false:unlocked:unspecified:disabled_by_configuration \
        true:locked:unspecified:host_session_locked \
        true:unlocked:unattended:host_unattended; do
    IFS=: read -r suspendable host_session attendance reason <<<"$suspend_case"
    set +e
    refusal="$("${lifecycle_env[@]}" MACVM_SUSPENDABLE="$suspendable" \
        MACHINE_CONTROL_HOST_SESSION="$host_session" \
        MACHINE_CONTROL_HOST_ATTENDANCE="$attendance" \
        MACHINE_CONTROL_TART_STATE=running \
        providers/tart-macos/provider.sh suspend 2>&1)"
    refusal_status=$?
    set -e
    [[ "$refusal_status" -eq 3 && "$refusal" == *"$reason"* ]]
    test ! -e "$mutation_marker"
done
set +e
refusal="$("${lifecycle_env[@]}" MACVM_SUSPENDABLE=false \
    MACHINE_CONTROL_TART_STATE=suspended \
    providers/tart-macos/provider.sh up 2>&1)"
refusal_status=$?
set -e
[[ "$refusal_status" -eq 3 && "$refusal" == *discard-suspended-state* ]]
test ! -e "$mutation_marker"
running_without_ip="$("${lifecycle_env[@]}" \
    MACHINE_CONTROL_TART_STATE=running \
    MACHINE_CONTROL_TART_IP_UNAVAILABLE=true \
    providers/tart-macos/provider.sh up)"
[[ "$running_without_ip" == running ]]
set +e
"${lifecycle_env[@]}" MACHINE_CONTROL_TART_STATE=running \
    MACHINE_CONTROL_TART_IP_UNAVAILABLE=true \
    providers/tart-macos/provider.sh ip >/dev/null 2>&1
ip_status=$?
set -e
[[ "$ip_status" -ne 0 ]]
set +e
refusal="$("${lifecycle_env[@]}" MACHINE_CONTROL_TART_STATE=stopped \
    providers/tart-macos/provider.sh discard-suspended-state 2>&1)"
refusal_status=$?
set -e
[[ "$refusal_status" -eq 3 && "$refusal" == *'not suspended'* ]]

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
    ([.checks[] | select(.id == "unlock_provider" and (.required | type) == "boolean")] | length) == 1' <<<"$guest_audit" >/dev/null

maintenance="$REPO_DIR/tests/fixtures/macvm-maintenance"
doctor_ready="$REPO_DIR/tests/fixtures/doctor-ready"
set +e
"$REPO_DIR/scripts/bounded-command.py" --seconds 1 -- /bin/sleep 5
bounded_status=$?
set -e
[[ "$bounded_status" -eq 124 ]]
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
# Build the installed protected components without installing on the controller.
"$REPO_DIR/guests/macos/unlock/build.sh" "$temporary/unlock-build" >/dev/null
/usr/bin/xcrun clang -fobjc-arc -Wall -Wextra -Werror -Wno-unused-function \
    "$REPO_DIR/../../tests/macos/session-observation.m" \
    -framework Foundation -framework IOKit -o "$temporary/session-observation"
"$temporary/session-observation"

python3 "$REPO_DIR/../../tests/macos/doctor-state.py"
python3 "$REPO_DIR/../../tests/macos/lock-screen-projection.py"
python3 "$REPO_DIR/../../tests/macos/session-probe-resources.py"
python3 "$REPO_DIR/../../tests/macos/maintenance-projection.py"

if [[ "$mode" == "--static" ]]; then
    printf 'macOS native static checks passed\n'
    exit 0
fi
# Everything above is isolated fixture work. The live tail must use the exact
# inventory-selected target and a disruptive claim supplied by its caller.
export MACHINE_CONTROL_CLAIM_POLICY=required
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
