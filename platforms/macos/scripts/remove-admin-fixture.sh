#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

macvm_require_host
macvm_assert_mutation_target

remote_source="/Users/$MACVM_GUEST_USER/Library/Application Support/macvm-testbed/AdminAuthorizationFixture.swift"
remote_app="/Users/$MACVM_GUEST_USER/Applications/Machine Control Admin Fixture.app"
remote_cache="/Users/$MACVM_GUEST_USER/Library/Caches/machine-control-admin-fixture"

macvm_exec /bin/rm -rf \
    "$remote_app" "$remote_cache"
macvm_exec /bin/rm -f "$remote_source"
