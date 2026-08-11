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

linuxvm_require_command jq
linuxvm_assert_candidate_target
if [[ "$($LINUXVM status 2>/dev/null || true)" != started ]]; then
    "$LINUXVM" up >/dev/null
fi

remote_bootstrap="/var/tmp/machine-control-bootstrap-$$.sh"
staged=false
cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM
    if [[ "$staged" == true &&
          "$remote_bootstrap" =~ ^/var/tmp/machine-control-bootstrap-[0-9]+\.sh$ ]]; then
        "$LINUXVM" exec -- /usr/bin/rm -f -- "$remote_bootstrap" \
            >/dev/null 2>&1 || true
    fi
    exit "$exit_code"
}
trap cleanup EXIT INT TERM

"$LINUXVM" push "$GUEST_BOOTSTRAP" "$remote_bootstrap"
staged=true
bootstrap_output="$($LINUXVM exec -- /usr/bin/bash "$remote_bootstrap" \
    --profile "$profile")"
bootstrap="$(printf '%s\n' "$bootstrap_output" | tail -n 1)"
if ! jq -e --arg profile "$profile" \
        '.schema == "machine-control-linux-bootstrap/v0" and
         .healthy == true and .profile == $profile' \
        <<<"$bootstrap" >/dev/null; then
    printf 'Guest package bootstrap returned no valid success report.\n' >&2
    exit 1
fi
"$LINUXVM" exec -- /usr/bin/rm -f -- "$remote_bootstrap"
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
