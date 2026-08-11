#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

macvm_require_host
macvm_assert_mutation_target

readonly remote_app="/Users/$MACVM_GUEST_USER/Applications/Machine Control Java Fixture.app"
readonly build_root="/Users/$MACVM_GUEST_USER/Library/Application Support/macvm-testbed/java-fixture-build"
readonly state_root="/Users/$MACVM_GUEST_USER/Library/Caches/machine-control-java-fixture"

macvm_exec /usr/bin/pkill -f \
    "$remote_app/Contents/MacOS/Machine Control Java Fixture" \
    >/dev/null 2>&1 || true
macvm_exec \
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -u "$remote_app" >/dev/null 2>&1 || true
macvm_exec /bin/rm -rf "$remote_app" "$build_root" "$state_root"

printf 'Removed the Java fixture and its state.\n'
