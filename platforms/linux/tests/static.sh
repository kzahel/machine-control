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
    "$REPO_DIR/guests/ubuntu/fixtures/browser_fixture.py" \
    "$REPO_DIR/guests/ubuntu/bootstrap/post_update.py"

"$PYTHON" -m unittest discover -s "$REPO_DIR/tests" \
    -p 'test_*.py' -v

"$REPO_DIR/bin/linuxvm" help >/dev/null
help_output="$($REPO_DIR/bin/linuxvm help)"
[[ "$help_output" == *'post-update audit|repair'* ]]
[[ "$help_output" == *'appliance-certify'* ]]
[[ "$help_output" == *'bootstrap [--profile'* ]]
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

maintenance="$REPO_DIR/tests/fixtures/linuxvm-maintenance"
doctor_ready="$REPO_DIR/tests/fixtures/doctor-ready"
maintenance_log="$temporary/maintenance.log"
maintenance_state="$temporary/maintenance.state"
maintenance_env=(
    env
    LINUXVM_CONFIG_FILE=/dev/null
    LINUXVM_REQUIRE_MUTATION_GUARD=false
    LINUXVM_TARGET_ROLE=candidate
    MACHINE_CONTROL_LINUXVM_LOG="$maintenance_log"
    MACHINE_CONTROL_LINUXVM_STATE="$maintenance_state"
)

audit="$(${maintenance_env[@]} \
    LINUXVM_POST_UPDATE_LINUXVM="$maintenance" \
    LINUXVM_POST_UPDATE_DOCTOR="$doctor_ready" \
    "$REPO_DIR/scripts/post-update.sh" audit --json)"
jq -e '.healthy == true and .operation == "audit" and
    .route == "qemu_guest_agent" and .reboot.observed == false' \
    <<<"$audit" >/dev/null
grep -q '^status ' "$maintenance_log"
! grep -q '^up ' "$maintenance_log"

: >"$maintenance_log"
printf 'stopped\n' >"$maintenance_state"
set +e
stopped_audit="$(${maintenance_env[@]} \
    LINUXVM_POST_UPDATE_LINUXVM="$maintenance" \
    LINUXVM_POST_UPDATE_DOCTOR="$doctor_ready" \
    "$REPO_DIR/scripts/post-update.sh" audit --json)"
stopped_status=$?
set -e
[[ "$stopped_status" -eq 1 ]]
jq -e '.failure == "target_not_running" and .healthy == false' \
    <<<"$stopped_audit" >/dev/null
[[ "$(wc -l <"$maintenance_log" | tr -d ' ')" -eq 1 ]]

: >"$maintenance_log"
repair="$(${maintenance_env[@]} \
    LINUXVM_POST_UPDATE_LINUXVM="$maintenance" \
    LINUXVM_POST_UPDATE_DOCTOR="$doctor_ready" \
    "$REPO_DIR/scripts/post-update.sh" repair --reboot --json)"
jq -e '.healthy == true and .operation == "repair" and
    .reboot == {requested:true,observed:true} and
    .post_update.mode == "audit"' <<<"$repair" >/dev/null
grep -q '^up ' "$maintenance_log"
grep -q '^reboot ' "$maintenance_log"

: >"$maintenance_log"
set +e
bad_nonce="$(${maintenance_env[@]} \
    MACHINE_CONTROL_LINUXVM_BAD_NONCE=1 \
    LINUXVM_POST_UPDATE_LINUXVM="$maintenance" \
    LINUXVM_POST_UPDATE_DOCTOR="$doctor_ready" \
    "$REPO_DIR/scripts/post-update.sh" audit --json 2>/dev/null)"
bad_nonce_status=$?
set -e
[[ "$bad_nonce_status" -eq 1 ]]
jq -e '.failure == "guest_agent_or_support_unavailable"' \
    <<<"$bad_nonce" >/dev/null

: >"$maintenance_log"
bootstrap="$(${maintenance_env[@]} \
    LINUXVM_BOOTSTRAP_LINUXVM="$maintenance" \
    "$REPO_DIR/scripts/bootstrap-appliance.sh" --profile runtime --json)"
jq -e '.healthy == true and .profile == "runtime" and
    .guest.profile == "runtime"' <<<"$bootstrap" >/dev/null
grep -q '^exec -- /usr/bin/systemd-run .*machine-control-bootstrap-' \
    "$maintenance_log"
grep -q '^deploy-resident ' "$maintenance_log"
grep -q '^post-update audit --profile runtime --json ' "$maintenance_log"

: >"$maintenance_log"
printf 'started\n' >"$maintenance_state"
if git -C "$REPO_DIR/../.." rev-parse --is-inside-work-tree \
        >/dev/null 2>&1; then
    certification="$(${maintenance_env[@]} \
        LINUXVM_CERTIFY_LINUXVM="$maintenance" \
        LINUXVM_CERTIFY_ALLOW_DIRTY_FOR_TESTS=1 \
        LINUXVM_CERTIFY_CHECK_TIMEOUT=60 \
        "$REPO_DIR/scripts/certify-appliance.sh" --json)"
    jq -e '.healthy == true and .final_power == "off" and
        .reboot.changedBootIdObserved == true and
        .guest_checks.portable_checks == "passed" and
        .guest_checks.native_checks == "passed" and
        .guest_checks.staging_removed == true' <<<"$certification" >/dev/null
    grep -q '^reboot ' "$maintenance_log"
    grep -q ' portable ' "$maintenance_log"
    grep -q ' native ' "$maintenance_log"
    grep -q '^shutdown ' "$maintenance_log"
    ! grep -Eq '(^| )(clone|workspace-|screenshot|click|type|key)( |$)' \
        "$maintenance_log"

    : >"$maintenance_log"
    printf 'started\n' >"$maintenance_state"
    set +e
    failed_certification="$(${maintenance_env[@]} \
        MACHINE_CONTROL_LINUXVM_NATIVE_FAIL=1 \
        LINUXVM_CERTIFY_LINUXVM="$maintenance" \
        LINUXVM_CERTIFY_ALLOW_DIRTY_FOR_TESTS=1 \
        LINUXVM_CERTIFY_CHECK_TIMEOUT=60 \
        "$REPO_DIR/scripts/certify-appliance.sh" --json)"
    failed_certification_status=$?
    set -e
    [[ "$failed_certification_status" -eq 1 ]]
    jq -e '.healthy == false and .final_power == "running" and
        .guest_checks.failure == "native_checks_failed" and
        .guest_checks.staging_removed == true' \
        <<<"$failed_certification" >/dev/null
    ! grep -q '^shutdown ' "$maintenance_log"
    grep -q '/usr/bin/rm -rf -- /var/tmp/machine-control-certify-' \
        "$maintenance_log"
fi

if ${maintenance_env[@]} \
        LINUXVM_BOOTSTRAP_LINUXVM="$maintenance" \
        LINUXVM_BOOTSTRAP_TIMEOUT=299 \
        "$REPO_DIR/scripts/bootstrap-appliance.sh" --json \
        >/dev/null 2>&1; then
    printf 'Linux bootstrap accepted an invalid timeout\n' >&2
    exit 1
fi

if ${maintenance_env[@]} \
        LINUXVM_CERTIFY_LINUXVM="$maintenance" \
        LINUXVM_CERTIFY_ALLOW_DIRTY_FOR_TESTS=1 \
        LINUXVM_CERTIFY_CHECK_TIMEOUT=59 \
        "$REPO_DIR/scripts/certify-appliance.sh" --json \
        >/dev/null 2>&1; then
    printf 'Linux certification accepted an invalid timeout\n' >&2
    exit 1
fi
printf 'Linux native static checks passed\n'
