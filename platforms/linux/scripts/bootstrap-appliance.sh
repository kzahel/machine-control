#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly LINUXVM="${LINUXVM_BOOTSTRAP_LINUXVM:-$LINUXVM_REPO_DIR/bin/linuxvm}"
readonly GUEST_BOOTSTRAP="$LINUXVM_REPO_DIR/guests/ubuntu/bootstrap/bootstrap-guest.sh"

usage() {
    cat <<'EOF'
Usage: linuxvm bootstrap [--profile development|runtime] [--json]

Installs an Ubuntu package profile and the checked-in resident on the exact
candidate. A missing QEMU guest agent still requires the visible bootstrap.
EOF
}

profile=development
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
        --json) shift ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

bootstrap_timeout="${LINUXVM_BOOTSTRAP_TIMEOUT:-1800}"
if [[ ! "$bootstrap_timeout" =~ ^[0-9]+$ ||
      "$bootstrap_timeout" -lt 300 || "$bootstrap_timeout" -gt 3600 ]]; then
    printf 'LINUXVM_BOOTSTRAP_TIMEOUT must be 300-3600 seconds.\n' >&2
    exit 2
fi

linuxvm_require_command jq
linuxvm_assert_candidate_target
if [[ "$($LINUXVM status 2>/dev/null || true)" != started ]]; then
    "$LINUXVM" up >/dev/null
fi

nonce="$(LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c 24 || true)"
if [[ ${#nonce} -ne 24 ]]; then
    printf 'Could not generate a bootstrap report nonce.\n' >&2
    exit 1
fi
remote_bootstrap="/var/tmp/machine-control-bootstrap-$nonce.sh"
remote_report="/var/tmp/machine-control-bootstrap-$nonce.json"
unit="machine-control-bootstrap-$nonce.service"
staged=false
cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM
    if [[ "$staged" == true &&
          "$remote_bootstrap" == "/var/tmp/machine-control-bootstrap-$nonce.sh" ]]; then
        "$LINUXVM" exec -- /usr/bin/rm -f -- \
            "$remote_bootstrap" "$remote_report" \
            >/dev/null 2>&1 || true
    fi
    exit "$exit_code"
}
trap cleanup EXIT INT TERM

"$LINUXVM" push "$GUEST_BOOTSTRAP" "$remote_bootstrap"
staged=true
"$LINUXVM" exec -- /usr/bin/systemd-run --quiet --collect \
    --unit "$unit" -- /usr/bin/bash "$remote_bootstrap" \
    --profile "$profile" --nonce "$nonce" --report-path "$remote_report"

deadline=$((SECONDS + bootstrap_timeout))
bootstrap=""
while (( SECONDS < deadline )); do
    if LINUXVM_EXEC_TIMEOUT=60 "$LINUXVM" exec -- /usr/bin/test -f \
            "$remote_report" >/dev/null 2>&1; then
        bootstrap="$(LINUXVM_EXEC_TIMEOUT=60 "$LINUXVM" exec -- \
            /usr/bin/cat "$remote_report" 2>/dev/null || true)"
        break
    fi
    sleep 2
done
if ! jq -e --arg profile "$profile" --arg nonce "$nonce" \
        '.schema == "machine-control-linux-bootstrap/v0" and
         .healthy == true and .profile == $profile and .nonce == $nonce' \
        <<<"$bootstrap" >/dev/null; then
    if jq -e --arg profile "$profile" --arg nonce "$nonce" \
            '.schema == "machine-control-linux-bootstrap/v0" and
             .profile == $profile and .nonce == $nonce' \
            <<<"$bootstrap" >/dev/null 2>&1; then
        printf 'Guest package bootstrap reported failure.\n' >&2
    else
        staged=false
        printf 'Guest package bootstrap did not return a valid report; the transient unit may still be running.\n' >&2
    fi
    exit 1
fi
"$LINUXVM" exec -- /usr/bin/rm -f -- "$remote_bootstrap" "$remote_report"
staged=false

"$LINUXVM" deploy-resident >/dev/null
audit="$($LINUXVM post-update audit --profile "$profile" --json)"
if ! jq -e '.healthy == true and .post_update.healthy == true and
        .doctor.ready == true' <<<"$audit" >/dev/null; then
    printf 'Linux package profile installed, but final readiness is unhealthy.\n' >&2
    exit 1
fi

jq -cn --arg profile "$profile" --argjson guest "$bootstrap" \
    --argjson audit "$audit" '{
        schema:"machine-control-linux-bootstrap-orchestration/v0",
        healthy:true,
        profile:$profile,
        guest:$guest,
        readiness:$audit
    }'
