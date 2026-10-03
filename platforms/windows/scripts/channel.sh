#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
source "$SCRIPT_DIR/resident-profile.sh"
[[ $# -eq 0 && "${WINVM_RESIDENT_PROFILE:-appliance}" == desktop ]] || {
    printf 'Admission channel requires the desktop resident profile\n' >&2; exit 2;
}
configuration="$(resident_profile_powershell)"
script="$configuration
\$callArguments[0] = 'channel'
& \$executable @callArguments
exit \$LASTEXITCODE"
winvm_powershell "$script"
