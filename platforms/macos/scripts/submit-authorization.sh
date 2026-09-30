#!/usr/bin/env bash

set -euo pipefail
set +x

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

macvm_require_host
macvm_assert_mutation_target

stored=false
binary="$(macvm_remote_ui_binary)"
endpoint="$(macvm_remote_control_socket)"
while [[ "${1:-}" == --* ]]; do
    case "$1" in
        --stored) stored=true ;;
        # Migration consent is granted by the retiring testbed resident,
        # which already holds Accessibility for its own identity.
        --legacy-resident)
            binary="$(macvm_remote_legacy_ui_app)/Contents/MacOS/macui"
            endpoint="$(macvm_remote_legacy_control_socket)"
            ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
    esac
    shift
done
if [[ $# -ne 1 || -z "$1" ]]; then
    printf 'Usage: macvm authorization-submit [--stored] [--legacy-resident] LEASE_ID\n' >&2
    exit 2
fi
readonly lease_id="$1" binary endpoint

if [[ "$stored" == true ]]; then
    # The canonical stored appliance credential streams from its owner-only
    # file into the one-shot channel; it never enters arguments or output.
    secret_file="${MACVM_ADMIN_SECRET_FILE:-}"
    if [[ -z "$secret_file" || ! -f "$secret_file" || -L "$secret_file" ||
          "$(/usr/bin/stat -f %Lp "$secret_file" 2>/dev/null)" != 600 ||
          "$(/usr/bin/stat -f %u "$secret_file" 2>/dev/null)" != "$(/usr/bin/id -u)" ||
          "$(/usr/bin/stat -f %z "$secret_file" 2>/dev/null)" == 0 ]]; then
        printf 'A nonempty owner-only guest credential file is required\n' >&2
        exit 1
    fi
    macvm_exec -i "$binary" credential "$endpoint" "$lease_id" < "$secret_file"
    exit
fi
if [[ ! -t 0 ]]; then
    printf 'Authorization submission requires an interactive terminal or --stored\n' >&2
    exit 2
fi

credential=''
trap 'unset credential' EXIT
printf 'Guest administrator credential: ' >&2
IFS= read -r -s credential
printf '\n' >&2
if [[ -z "$credential" ]]; then
    printf 'Credential must not be empty\n' >&2
    exit 2
fi

printf '%s' "$credential" | macvm_exec -i "$binary" credential "$endpoint" "$lease_id"
