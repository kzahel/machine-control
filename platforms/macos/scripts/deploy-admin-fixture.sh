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

"$MACVM_TART" exec "$MACVM_NAME" /bin/mkdir -p \
    "$(/usr/bin/dirname "$remote_source")" "$remote_contents/MacOS"
"$MACVM_TART" exec -i "$MACVM_NAME" /usr/bin/tee "$remote_source" \
    < "$source_file" >/dev/null
"$MACVM_TART" exec -i "$MACVM_NAME" /usr/bin/tee \
    "$remote_contents/Info.plist" < "$info_file" >/dev/null
"$MACVM_TART" exec "$MACVM_NAME" /usr/bin/xcrun swiftc -O \
    -framework AppKit -o "$remote_binary" "$remote_source"
"$MACVM_TART" exec "$MACVM_NAME" /bin/chmod 755 "$remote_binary"
"$MACVM_TART" exec "$MACVM_NAME" /usr/bin/codesign --force --deep --sign - \
    --identifier org.machine-control.admin-fixture "$remote_app"
"$MACVM_TART" exec "$MACVM_NAME" \
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -f "$remote_app"

printf 'Deployed %s\n' "$remote_app"
