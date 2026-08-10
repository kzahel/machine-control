#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

macvm_require_host
macvm_assert_mutation_target

remote_source="/Users/$MACVM_GUEST_USER/Library/Application Support/macvm-testbed/MachineControlFixture.swift"
remote_app="/Users/$MACVM_GUEST_USER/Applications/Machine Control Fixture.app"
remote_cache="/Users/$MACVM_GUEST_USER/Library/Caches/machine-control-fixture"
surface_root="/Users/$MACVM_GUEST_USER/Documents/MachineControlSurfaceCorpus"

macvm_exec /usr/bin/killall MachineControlFixture >/dev/null 2>&1 || true
macvm_exec \
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -u "$remote_app" >/dev/null 2>&1 || true
macvm_exec /bin/rm -rf \
    "$remote_app" "$remote_source" "$remote_cache" "$surface_root"

printf 'Removed the AppKit fixture and its state.\n'
