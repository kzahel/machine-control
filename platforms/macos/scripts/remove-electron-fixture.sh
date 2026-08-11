#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

macvm_require_host
macvm_assert_mutation_target

readonly remote_app="/Users/$MACVM_GUEST_USER/Applications/Machine Control Electron Fixture.app"
readonly state_root="/Users/$MACVM_GUEST_USER/Library/Caches/machine-control-electron-fixture"

macvm_exec /usr/bin/pkill -f \
    "$remote_app/Contents/MacOS/Electron" >/dev/null 2>&1 || true
macvm_exec \
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -u "$remote_app" >/dev/null 2>&1 || true
macvm_exec /bin/rm -rf "$remote_app" "$state_root"

printf 'Removed the Electron fixture and its state.\n'
