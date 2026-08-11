#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

macvm_require_host
macvm_assert_mutation_target

source_file="$MACVM_REPO_DIR/guests/macos/admin-fixture/AdminAuthorizationFixture.swift"
info_file="$MACVM_REPO_DIR/guests/macos/admin-fixture/Info.plist"
remote_source="/Users/$MACVM_GUEST_USER/Library/Application Support/macvm-testbed/AdminAuthorizationFixture.swift"
remote_app="/Users/$MACVM_GUEST_USER/Applications/Machine Control Admin Fixture.app"
remote_contents="$remote_app/Contents"
remote_binary="$remote_contents/MacOS/AdminAuthorizationFixture"

macvm_exec /bin/mkdir -p \
    "$(/usr/bin/dirname "$remote_source")" "$remote_contents/MacOS"
macvm_exec -i /usr/bin/tee "$remote_source" \
    < "$source_file" >/dev/null
macvm_exec -i /usr/bin/tee \
    "$remote_contents/Info.plist" < "$info_file" >/dev/null
macvm_exec /usr/bin/xcrun swiftc -O \
    -framework AppKit -o "$remote_binary" "$remote_source"
macvm_exec /bin/chmod 755 "$remote_binary"
macvm_exec /usr/bin/codesign --force --deep --sign - \
    --identifier org.machine-control.admin-fixture "$remote_app"
macvm_exec \
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -f "$remote_app"

printf 'Deployed %s\n' "$remote_app"
