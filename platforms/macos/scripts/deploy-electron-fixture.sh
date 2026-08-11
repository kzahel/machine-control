#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

macvm_require_host
macvm_assert_mutation_target

readonly source_root="$MACVM_REPO_DIR/guests/macos/electron-fixture"
readonly runtime_root="/Users/$MACVM_GUEST_USER/Library/Application Support/macvm-testbed/framework-runtimes"
readonly remote_app="/Users/$MACVM_GUEST_USER/Applications/Machine Control Electron Fixture.app"
readonly remote_resources="$remote_app/Contents/Resources/app"

"$SCRIPT_DIR/framework-runtime-status.sh" \
    | jq -e '.ready == true' >/dev/null \
    || { printf 'Install framework runtimes before deploying fixtures.\n' >&2; exit 1; }

macvm_exec /bin/rm -rf "$remote_app"
macvm_exec /usr/bin/ditto "$runtime_root/Electron.app" "$remote_app"
macvm_exec /bin/rm -rf "$remote_resources"
macvm_exec /bin/mkdir -p "$remote_resources"
for source in package.json main.js preload.js index.html; do
    macvm_exec -i /usr/bin/tee "$remote_resources/$source" \
        < "$source_root/$source" >/dev/null
done
macvm_exec /usr/libexec/PlistBuddy -c \
    'Set :CFBundleIdentifier org.machine-control.electron-fixture' \
    "$remote_app/Contents/Info.plist"
macvm_exec /usr/libexec/PlistBuddy -c \
    'Set :CFBundleName Machine Control Electron Fixture' \
    "$remote_app/Contents/Info.plist"
macvm_exec /usr/libexec/PlistBuddy -c \
    'Set :CFBundleDisplayName Machine Control Electron Fixture' \
    "$remote_app/Contents/Info.plist"
macvm_exec /usr/bin/codesign --force --deep --sign - \
    --identifier org.machine-control.electron-fixture "$remote_app"
macvm_exec \
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -f "$remote_app"

printf 'Deployed %s\n' "$remote_app"
