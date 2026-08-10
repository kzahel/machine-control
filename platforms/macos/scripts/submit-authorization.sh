#!/usr/bin/env bash

set -euo pipefail
set +x

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

macvm_require_host
macvm_assert_mutation_target

if [[ $# -ne 1 || -z "$1" ]]; then
    printf 'Usage: macvm authorization-submit LEASE_ID\n' >&2
    exit 2
fi
if [[ ! -t 0 ]]; then
    printf 'Authorization submission requires an interactive terminal\n' >&2
    exit 2
fi

readonly lease_id="$1"
credential=''
trap 'unset credential' EXIT
printf 'Guest administrator credential: ' >&2
IFS= read -r -s credential
printf '\n' >&2
if [[ -z "$credential" ]]; then
    printf 'Credential must not be empty\n' >&2
    exit 2
fi

printf '%s' "$credential" | macvm_exec -i \
    "$(macvm_remote_ui_binary)" credential \
    "$(macvm_remote_control_socket)" "$lease_id"
