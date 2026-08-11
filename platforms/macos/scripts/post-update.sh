#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly MACVM="${MACVM_POST_UPDATE_MACVM:-$MACVM_REPO_DIR/bin/macvm}"
readonly DOCTOR="${MACVM_POST_UPDATE_DOCTOR:-$MACVM_REPO_DIR/scripts/doctor-json.sh}"
readonly DEPLOY_UI="${MACVM_POST_UPDATE_DEPLOY_UI:-$MACVM_REPO_DIR/scripts/deploy-ui.sh}"
readonly DEPLOY_MAINTENANCE="${MACVM_POST_UPDATE_DEPLOY_MAINTENANCE:-$MACVM_REPO_DIR/scripts/deploy-maintenance.sh}"
readonly GUEST_SCRIPT="$(macvm_remote_post_update_script)"

usage() {
    cat <<'EOF'
Usage: macvm post-update audit|repair [--profile development|runtime]
                                     [--reboot] [--json]

Audit is read-only and refuses a stopped target. Repair is exact-candidate
only, redeploys the stable resident/support identity, and changes only its
enumerated launchd jobs. Reboot is explicit.
EOF
}

operation="${1:-}"
if [[ "$operation" != audit && "$operation" != repair ]]; then
    usage >&2
    exit 2
fi
shift
profile=development
reboot=false
while (( $# > 0 )); do
    case "$1" in
        --profile)
            if (( $# < 2 )) ||
                    [[ "$2" != development && "$2" != runtime ]]; then
                usage >&2
                exit 2
            fi
            profile="$2"
            shift 2
            ;;
        --reboot) reboot=true; shift ;;
        --json) shift ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done
if [[ "$operation" == audit && "$reboot" == true ]]; then
    printf 'Reboot is valid only with post-update repair.\n' >&2
    exit 2
fi

macvm_require_command jq
nonce="$(LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c 24 || true)"
if [[ ${#nonce} -ne 24 ]]; then
    printf 'Could not generate a post-update report nonce.\n' >&2
    exit 1
fi

validate_guest_report() {
    local report="$1" expected_mode="$2"
    jq -e --arg nonce "$nonce" --arg mode "$expected_mode" \
        --arg profile "$profile" \
        '.schema == "machine-control-macos-post-update/v0" and
         .nonce == $nonce and .mode == $mode and .profile == $profile and
         (.healthy | type) == "boolean" and (.checks | type) == "array"' \
        <<<"$report" >/dev/null
}

run_guest() {
    local mode="$1" output status
    set +e
    output="$($MACVM exec "$GUEST_SCRIPT" --mode "$mode" \
        --profile "$profile" --nonce "$nonce" 2>/dev/null)"
    status=$?
    set -e
    output="$(printf '%s\n' "$output" | tail -n 1)"
    if ! validate_guest_report "$output" "$mode"; then
        printf 'Installed macOS maintenance support returned no valid report (status %s).\n' \
            "$status" >&2
        return 1
    fi
    printf '%s\n' "$output"
}

run_doctor() {
    local output
    set +e
    output="$($DOCTOR 2>/dev/null)"
    set -e
    if ! jq -e '.schema == "machine-control-doctor/v0"' \
            <<<"$output" >/dev/null 2>&1; then
        return 1
    fi
    printf '%s\n' "$output"
}

wait_for_ready_doctor() {
    local deadline=$((SECONDS + MACVM_BOOT_TIMEOUT)) output=""
    while (( SECONDS < deadline )); do
        output="$(run_doctor || true)"
        if jq -e '.ready == true' <<<"$output" >/dev/null 2>&1; then
            printf '%s\n' "$output"
            return 0
        fi
        sleep 2
    done
    [[ -z "$output" ]] || printf '%s\n' "$output"
    return 1
}

guest_boot_epoch() {
    local value
    value="$($MACVM exec /usr/sbin/sysctl -n kern.boottime 2>/dev/null)" || return
    if [[ "$value" =~ sec[[:space:]]*=[[:space:]]*([0-9]+) ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
        return 0
    fi
    return 1
}

if [[ "$operation" == repair ]]; then
    macvm_assert_candidate_target
fi

power_state="$($MACVM status 2>/dev/null || true)"
if [[ "$operation" == audit && "$power_state" != running ]]; then
    jq -cn --arg power "${power_state:-unknown}" '{
        schema:"machine-control-macos-post-update-orchestration/v0",
        operation:"audit",route:"unavailable",healthy:false,
        power:$power,reboot:{requested:false,observed:false},
        post_update:null,doctor:null,failure:"target_not_running"
    }'
    exit 1
elif [[ "$operation" == repair && "$power_state" != running ]]; then
    "$MACVM" up >/dev/null
fi

if [[ "$operation" == repair ]]; then
    "$DEPLOY_UI" >/dev/null
    "$DEPLOY_MAINTENANCE" >/dev/null
fi

if ! guest="$(run_guest "$operation")"; then
    jq -cn --arg operation "$operation" --argjson requested "$reboot" '{
        schema:"machine-control-macos-post-update-orchestration/v0",
        operation:$operation,route:"unavailable",healthy:false,
        reboot:{requested:$requested,observed:false},post_update:null,
        doctor:null,failure:"guest_agent_or_support_unavailable"
    }'
    exit 1
fi

reboot_observed=false
if [[ "$reboot" == true ]]; then
    initial_epoch="$(guest_boot_epoch)"
    "$MACVM" exec /usr/bin/sudo -n /sbin/shutdown -r now \
        >/dev/null 2>&1 || true
    deadline=$((SECONDS + MACVM_BOOT_TIMEOUT))
    while (( SECONDS < deadline )); do
        current_epoch="$(guest_boot_epoch 2>/dev/null || true)"
        if [[ -n "$current_epoch" && "$current_epoch" != "$initial_epoch" ]]; then
            reboot_observed=true
            break
        fi
        sleep 2
    done
    if [[ "$reboot_observed" != true ]]; then
        printf 'macOS reboot did not produce a changed boot epoch.\n' >&2
        exit 1
    fi
    while (( SECONDS < deadline )); do
        guest="$(run_guest audit || true)"
        if validate_guest_report "$guest" audit &&
                jq -e '.healthy == true' <<<"$guest" >/dev/null 2>&1; then
            break
        fi
        sleep 2
    done
    if ! validate_guest_report "$guest" audit; then
        printf 'No valid macOS audit returned after reboot.\n' >&2
        exit 1
    fi
fi

doctor="$(wait_for_ready_doctor || true)"
doctor_ready=false
if jq -e '.ready == true' <<<"$doctor" >/dev/null 2>&1; then
    doctor_ready=true
elif ! jq -e '.schema == "machine-control-doctor/v0"' \
        <<<"$doctor" >/dev/null 2>&1; then
    doctor=null
fi

healthy=false
if [[ "$(jq -r '.healthy' <<<"$guest")" == true &&
      "$doctor_ready" == true &&
      ( "$reboot" == false || "$reboot_observed" == true ) ]]; then
    healthy=true
fi

jq -cn --arg operation "$operation" --argjson healthy "$healthy" \
    --argjson requested "$reboot" --argjson observed "$reboot_observed" \
    --argjson postUpdate "$guest" --argjson doctor "$doctor" '{
        schema:"machine-control-macos-post-update-orchestration/v0",
        operation:$operation,
        route:"selected_guest_transport",
        healthy:$healthy,
        reboot:{requested:$requested,observed:$observed},
        post_update:$postUpdate,
        doctor:$doctor
    }'
[[ "$healthy" == true ]]
