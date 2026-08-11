#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly WINVM="$WINVM_REPO_DIR/bin/winvm"
readonly PROVIDER="$(winvm_provider_path)"
readonly GUEST_SCRIPT='C:\ProgramData\MachineControl\runtime\support\post-update.ps1'
readonly DOCTOR="${WINVM_POST_UPDATE_DOCTOR:-$WINVM_REPO_DIR/scripts/doctor-json.sh}"

usage() {
    cat <<'EOF'
Usage: winvm post-update audit|repair [--profile development|runtime]
                                     [--reboot] [--json]

Audit is read-only and requires key-only SSH. Repair is candidate-only,
prefers SSH, and may fall back to nonce-attested guest-agent execution.
Reboot is valid only with repair and remains explicit.
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
while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)
            if [[ $# -lt 2 ||
                ( "$2" != development && "$2" != runtime ) ]]; then
                usage >&2
                exit 2
            fi
            profile="$2"
            shift 2
            ;;
        --reboot)
            reboot=true
            shift
            ;;
        --json)
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            usage >&2
            exit 2
            ;;
    esac
done
if [[ "$operation" == audit && "$reboot" == true ]]; then
    printf 'Reboot is valid only with post-update repair.\n' >&2
    exit 2
fi

for tool in jq iconv base64; do
    winvm_require_command "$tool"
done

case "$profile" in
    development) profile_title=Development ;;
    runtime) profile_title=Runtime ;;
esac
nonce="$(LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c 24 || true)"
if [[ ${#nonce} -ne 24 ]]; then
    printf 'Could not generate a post-update report nonce.\n' >&2
    exit 1
fi

ssh_available() {
    "$WINVM_SSH_BIN" -o BatchMode=yes -o ConnectTimeout=10 \
        "$WINVM_SSH_HOST" exit >/dev/null 2>&1
}

validate_guest_report() {
    local report="$1" expected_mode="$2"
    jq -e --arg nonce "$nonce" --arg mode "$expected_mode" \
        '.schema == "machine-control-windows-post-update/v0" and
         .nonce == $nonce and .mode == $mode and
         (.healthy | type) == "boolean" and
         (.checks | type) == "array"' <<<"$report" >/dev/null
}

run_guest_over_ssh() {
    local mode="$1" expected_mode output status
    case "$mode" in
        Audit) expected_mode=audit ;;
        Repair) expected_mode=repair ;;
        *) return 2 ;;
    esac
    set +e
    output="$($WINVM_SSH_BIN -o BatchMode=yes -o ConnectTimeout=15 \
        "$WINVM_SSH_HOST" \
        "powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"$GUEST_SCRIPT\" -Mode '$mode' -Profile '$profile_title' -Nonce '$nonce'" \
        2>/dev/null)"
    status=$?
    set -e
    output="$(printf '%s\n' "$output" | tr -d '\r' | tail -n 1)"
    if ! validate_guest_report "$output" "$expected_mode"; then
        printf 'Installed post-update script returned no valid report (status %s).\n' \
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

wait_for_ssh() {
    local deadline=$((SECONDS + WINVM_BOOT_TIMEOUT))
    while (( SECONDS < deadline )); do
        if ssh_available; then return 0; fi
        sleep 2
    done
    return 1
}

wait_for_ready_doctor() {
    local deadline=$((SECONDS + WINVM_BOOT_TIMEOUT)) output=""
    while (( SECONDS < deadline )); do
        output="$(run_doctor || true)"
        if jq -e '.ready == true' <<<"$output" >/dev/null 2>&1; then
            printf '%s\n' "$output"
            return 0
        fi
        sleep 2
    done
    if [[ -n "$output" ]]; then printf '%s\n' "$output"; fi
    return 1
}

cleanup_guest_agent_stage() {
    local encoded
    read -r -d '' cleanup_script <<POWERSHELL || true
Remove-Item -LiteralPath 'C:\Users\Public\winvm-post-update-$nonce.ps1' -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath 'C:\ProgramData\MachineControl\reports\post-update-$nonce.json' -Force -ErrorAction SilentlyContinue
POWERSHELL
    encoded="$(printf '%s' "$cleanup_script" | winvm_encode_powershell)"
    "$WINVM_SSH_BIN" -o BatchMode=yes -o ConnectTimeout=10 \
        "$WINVM_SSH_HOST" \
        "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand $encoded" \
        >/dev/null 2>&1 || true
}

if [[ "$operation" == repair ]]; then
    "$PROVIDER" assert-target post-update-repair >/dev/null
else
    "$PROVIDER" assert-target connect >/dev/null
fi

power_state="$($PROVIDER status 2>/dev/null || true)"
if [[ "$operation" == audit && "$power_state" != started ]]; then
    jq -cn --arg state "${power_state:-unknown}" '{
        schema:"machine-control-windows-post-update-orchestration/v0",
        operation:"audit",route:"unavailable",healthy:false,
        power:$state,reboot:{requested:false,observed:false},
        post_update:null,doctor:null,failure:"target_not_running"
    }'
    exit 1
elif [[ "$operation" == repair && "$power_state" != started ]]; then
    "$PROVIDER" up >/dev/null
fi

route=key_only_ssh
if ssh_available; then
    case "$operation" in
        audit) guest="$(run_guest_over_ssh Audit)" ;;
        repair) guest="$(run_guest_over_ssh Repair)" ;;
    esac
elif [[ "$operation" == repair ]]; then
    route=utm_guest_agent
    guest="$($PROVIDER post-update-guest-agent "$profile_title" "$nonce")"
    validate_guest_report "$guest" repair
    if ! wait_for_ssh; then
        jq -cn --arg route "$route" --argjson audit "$guest" '{
            schema:"machine-control-windows-post-update-orchestration/v0",
            operation:"repair",route:$route,healthy:false,
            reboot:{requested:false,observed:false},post_update:$audit,
            doctor:null,failure:"key_only_ssh_not_restored"
        }'
        exit 1
    fi
    cleanup_guest_agent_stage
else
    jq -cn '{
        schema:"machine-control-windows-post-update-orchestration/v0",
        operation:"audit",route:"unavailable",healthy:false,
        reboot:{requested:false,observed:false},post_update:null,
        doctor:null,failure:"key_only_ssh_unavailable"
    }'
    exit 1
fi

initial_epoch="$(jq -r '.boot_epoch_utc' <<<"$guest")"
reboot_observed=false
if [[ "$reboot" == true ]]; then
    "$WINVM_SSH_BIN" -o BatchMode=yes -o ConnectTimeout=10 \
        "$WINVM_SSH_HOST" 'shutdown.exe /r /t 0' >/dev/null 2>&1 || true
    if ! wait_for_ssh; then
        printf 'Key-only SSH did not return after reboot.\n' >&2
        exit 1
    fi
    deadline=$((SECONDS + WINVM_BOOT_TIMEOUT))
    while (( SECONDS < deadline )); do
        guest="$(run_guest_over_ssh Audit || true)"
        if validate_guest_report "$guest" audit &&
            [[ "$(jq -r '.boot_epoch_utc' <<<"$guest")" != "$initial_epoch" ]]; then
            reboot_observed=true
            break
        fi
        sleep 2
    done
    if [[ "$reboot_observed" != true ]]; then
        printf 'Windows reboot did not produce a changed boot epoch.\n' >&2
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

jq -cn \
    --arg operation "$operation" \
    --arg route "$route" \
    --argjson healthy "$healthy" \
    --argjson requested "$reboot" \
    --argjson observed "$reboot_observed" \
    --argjson post_update "$guest" \
    --argjson doctor "$doctor" \
    '{
        schema:"machine-control-windows-post-update-orchestration/v0",
        operation:$operation,
        route:$route,
        healthy:$healthy,
        reboot:{requested:$requested,observed:$observed},
        post_update:$post_update,
        doctor:$doctor
    }'
[[ "$healthy" == true ]]
