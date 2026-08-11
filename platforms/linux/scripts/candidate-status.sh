#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly PROVIDER="$(linuxvm_provider_path)"

if [[ "${1:-}" != "--json" || $# -ne 1 ]]; then
    printf 'Usage: linuxvm candidate-status --json\n' >&2
    exit 2
fi

linuxvm_assert_mutation_target
if [[ "$LINUXVM_TARGET_ROLE" != candidate ]]; then
    printf 'The exact target is not classified as a candidate\n' >&2
    exit 1
fi

inventory="$($LINUXVM_REPO_DIR/providers/$LINUXVM_PROVIDER/workspace.sh \
    workspace-inventory --json)"
workspace_ownership=present
if jq -e '.data.counts.temporary == 0 and .data.counts.retained == 0' \
        <<<"$inventory" >/dev/null; then
    workspace_ownership=clear
fi

case "$($PROVIDER status 2>/dev/null || true)" in
    started|running) power_state=running ;;
    stopped|off) power_state=off ;;
    suspended|paused|saved) power_state=suspended ;;
    starting) power_state=starting ;;
    *) power_state=unknown ;;
esac

jq -cn \
    --arg powerState "$power_state" \
    --arg workspaceOwnership "$workspace_ownership" \
    '{
        schema:"machine-control-candidate-assertion/v0",
        identityPin:"verified",
        role:"candidate",
        powerState:$powerState,
        workspaceOwnership:$workspaceOwnership
    }'
