#!/usr/bin/env bash
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
result="$("$SCRIPT_DIR/doctor-json.sh")"
status=$?
if ! jq -e '.schema == "machine-control-doctor/v0"' <<<"$result" >/dev/null; then
    printf '%s\n' "$result" >&2; exit 1
fi
jq -r '.checks[] | "[\(.status)] \(.id): \(.summary)"' <<<"$result"
jq -r '"Desktop: \(.states.desktop); unlock: \(.extensions.unlock.readiness // "unknown")"' <<<"$result"
exit "$status"
