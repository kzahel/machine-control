#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

if [[ "${1:-}" != --json || $# -ne 1 ]]; then
    printf 'Usage: macvm candidate-status --json\n' >&2
    exit 2
fi

macvm_assert_candidate_target
inventory="$($MACVM_REPO_DIR/providers/tart-macos/workspace.sh \
    workspace-inventory --json)"
workspace_ownership=present
if jq -e '.data.counts.temporary == 0 and .data.counts.retained == 0' \
        <<<"$inventory" >/dev/null; then
    workspace_ownership=clear
fi

case "$(macvm_state 2>/dev/null || true)" in
    running) power_state=running ;;
    stopped|off) power_state=off ;;
    suspended|paused|saved) power_state=suspended ;;
    starting) power_state=starting ;;
    *) power_state=unknown ;;
esac

jq -cn --arg powerState "$power_state" \
    --arg workspaceOwnership "$workspace_ownership" '{
        schema:"machine-control-candidate-assertion/v0",
        identityPin:"verified",role:"candidate",
        powerState:$powerState,workspaceOwnership:$workspaceOwnership
    }'
