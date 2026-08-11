#!/usr/bin/env bash
set -euo pipefail
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
macvm_require_host
macvm_assert_mutation_target
source_file="$MACVM_REPO_DIR/guests/macos/privacy-fixture/PrivacyConsentFixture.swift"
info_file="$MACVM_REPO_DIR/guests/macos/privacy-fixture/Info.plist"
remote_source="/Users/$MACVM_GUEST_USER/Library/Application Support/macvm-testbed/PrivacyConsentFixture.swift"
remote_app="/Users/$MACVM_GUEST_USER/Applications/Machine Control Privacy Fixture.app"
remote_contents="$remote_app/Contents"
remote_binary="$remote_contents/MacOS/PrivacyConsentFixture"
macvm_exec /bin/mkdir -p "$(/usr/bin/dirname "$remote_source")" "$remote_contents/MacOS"
macvm_exec -i /usr/bin/tee "$remote_source" <"$source_file" >/dev/null
macvm_exec -i /usr/bin/tee "$remote_contents/Info.plist" <"$info_file" >/dev/null
macvm_exec /usr/bin/xcrun swiftc -O -framework AppKit \
    -framework ApplicationServices -framework AVFoundation -framework Network \
    -framework ScreenCaptureKit -framework UserNotifications \
    -o "$remote_binary" "$remote_source"
macvm_exec /bin/chmod 755 "$remote_binary"
macvm_exec /usr/bin/codesign --force --deep --sign - \
    --identifier org.machine-control.privacy-fixture "$remote_app"
macvm_exec /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -f "$remote_app"
printf 'Deployed %s\n' "$remote_app"
