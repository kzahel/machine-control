#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly MACVM="${MACVM_BOOTSTRAP_MACVM:-$MACVM_REPO_DIR/bin/macvm}"
readonly DEPLOY_UI="${MACVM_BOOTSTRAP_DEPLOY_UI:-$MACVM_REPO_DIR/scripts/deploy-ui.sh}"
readonly DEPLOY_MAINTENANCE="${MACVM_BOOTSTRAP_DEPLOY_MAINTENANCE:-$MACVM_REPO_DIR/scripts/deploy-maintenance.sh}"

usage() {
    cat <<'EOF'
Usage: macvm bootstrap [--profile development|runtime] [--json]

Deploys the checked-in resident and maintenance support without invoking an
interactive package installer or changing macOS consent.
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
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

macvm_require_command jq
macvm_assert_candidate_target
if [[ "$($MACVM status 2>/dev/null || true)" != running ]]; then
    "$MACVM" up >/dev/null
fi

tool_check='set -e; /usr/bin/xcrun --find swiftc >/dev/null; /bin/test -x /usr/bin/codesign; /usr/bin/plutil -help >/dev/null 2>&1'
if [[ "$profile" == development ]]; then
    tool_check+='; /usr/bin/xcrun --find git >/dev/null; /bin/test -x /usr/bin/python3'
fi
if ! "$MACVM" exec /bin/bash -c "$tool_check" >/dev/null 2>&1; then
    jq -cn --arg profile "$profile" '{
        schema:"machine-control-macos-bootstrap/v0",healthy:false,
        profile:$profile,profile_tools:"missing",
        maintenance:null,failure:"profile_tools_missing"
    }'
    exit 1
fi

"$DEPLOY_UI" >/dev/null
"$DEPLOY_MAINTENANCE" >/dev/null
set +e
maintenance="$($MACVM post-update audit --profile "$profile" --json)"
maintenance_status=$?
set -e
healthy=false
if [[ "$maintenance_status" -eq 0 ]] &&
        jq -e '.schema == "machine-control-macos-post-update-orchestration/v0"
            and .healthy == true' <<<"$maintenance" >/dev/null 2>&1; then
    healthy=true
elif ! jq -e '.schema == "machine-control-macos-post-update-orchestration/v0"' \
        <<<"$maintenance" >/dev/null 2>&1; then
    maintenance=null
fi

jq -cn --arg profile "$profile" --argjson healthy "$healthy" \
    --argjson maintenance "$maintenance" '{
        schema:"machine-control-macos-bootstrap/v0",healthy:$healthy,
        profile:$profile,profile_tools:"available",maintenance:$maintenance
    }'
[[ "$healthy" == true ]]
