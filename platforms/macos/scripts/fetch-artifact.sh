#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

if [[ $# -lt 1 || $# -gt 2 ]]; then
    printf 'Usage: macvm artifact-fetch GUEST_ARTIFACT [LOCAL_FILE]\n' >&2
    exit 2
fi

readonly guest_path="$1"
readonly allowed_root="/Users/$MACVM_GUEST_USER/Library/Caches/machine-control/artifacts/"
case "$guest_path" in
    "$allowed_root"*) ;;
    *)
        printf 'Refusing artifact path outside the resident artifact root\n' >&2
        exit 2
        ;;
esac
if [[ "$guest_path" == *'/../'* || "$guest_path" == *'/./'* ]]; then
    printf 'Refusing non-canonical artifact path\n' >&2
    exit 2
fi

if [[ $# -eq 2 ]]; then
    output="$2"
    /bin/mkdir -p "$(/usr/bin/dirname "$output")"
else
    output_directory="$(/usr/bin/mktemp -d /tmp/macvm-artifact.XXXXXX)"
    output="$output_directory/${guest_path##*/}"
fi

scratch="$(/usr/bin/mktemp "${output}.partial.XXXXXX")"
trap '/bin/rm -f "$scratch"' EXIT
macvm_exec /bin/cat "$guest_path" >"$scratch"
if [[ ! -s "$scratch" ]]; then
    printf 'Guest artifact is empty: %s\n' "$guest_path" >&2
    exit 1
fi
/bin/mv -f "$scratch" "$output"
trap - EXIT
printf '%s\n' "$output"
