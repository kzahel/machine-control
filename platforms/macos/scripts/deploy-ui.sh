#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

macvm_require_host
macvm_assert_mutation_target

force=0
case "${1:-}" in
    '') ;;
    --force) force=1 ;;
    -h|--help)
        printf 'Usage: macvm deploy-ui [--force]\n'
        exit 0
        ;;
    *)
        printf 'Unknown deploy-ui option: %s\n' "$1" >&2
        exit 2
        ;;
esac

source_file="$MACVM_REPO_DIR/guests/macos/ui/macui.swift"
info_file="$MACVM_REPO_DIR/guests/macos/ui/Info.plist"
control_cli_file="$MACVM_REPO_DIR/guests/macos/ui/machine-control"
remote_directory="$(macvm_remote_ui_dir)"
remote_source="$remote_directory/macui.swift"
remote_app="$(macvm_remote_ui_app)"
remote_contents="$remote_app/Contents"
remote_binary="$(macvm_remote_ui_binary)"
remote_control_cli="$(macvm_remote_control_cli)"
remote_socket="$(macvm_remote_control_socket)"

if ! "$MACVM_TART" exec "$MACVM_NAME" /usr/bin/true; then
    printf 'Tart guest agent is unavailable; read docs/bootstrap.md\n' >&2
    exit 1
fi

if ! "$MACVM_TART" exec "$MACVM_NAME" /usr/bin/xcrun --find swiftc >/dev/null; then
    printf 'Guest Xcode Command Line Tools are required to compile macui\n' >&2
    exit 1
fi

if (( ! force )) \
        && "$MACVM_TART" exec "$MACVM_NAME" /bin/test -x "$remote_binary" \
            >/dev/null 2>&1 \
        && "$MACVM_TART" exec "$MACVM_NAME" /bin/test -f "$remote_source" \
            >/dev/null 2>&1 \
        && "$MACVM_TART" exec "$MACVM_NAME" /bin/test -f \
            "$remote_contents/Info.plist" >/dev/null 2>&1; then
    local_source_hash="$(/usr/bin/shasum -a 256 "$source_file" | /usr/bin/awk '{print $1}')"
    local_info_hash="$(/usr/bin/shasum -a 256 "$info_file" | /usr/bin/awk '{print $1}')"
    remote_source_hash="$(
        "$MACVM_TART" exec "$MACVM_NAME" /usr/bin/shasum -a 256 "$remote_source" \
            | /usr/bin/awk '{print $1}'
    )"
    remote_info_hash="$(
        "$MACVM_TART" exec "$MACVM_NAME" /usr/bin/shasum -a 256 \
            "$remote_contents/Info.plist" | /usr/bin/awk '{print $1}'
    )"
    if [[ "$local_source_hash" == "$remote_source_hash" \
            && "$local_info_hash" == "$remote_info_hash" ]]; then
        printf 'MacVM UI is already current at %s\n' "$remote_app"
        "$MACVM_REPO_DIR/bin/macui" resident-start >/dev/null
        "$MACVM_REPO_DIR/bin/macui" control '{"operation":"status"}'
        exit 0
    fi
fi

# A prior resident may still have the old executable mapped. Ask it to stop
# before replacement; an absent or older service is harmless here.
"$MACVM_REPO_DIR/bin/macui" resident-stop >/dev/null 2>&1 || true

"$MACVM_TART" exec "$MACVM_NAME" /bin/mkdir -p \
    "$remote_directory" "$remote_contents/MacOS" "$remote_contents/Resources"
"$MACVM_TART" exec -i "$MACVM_NAME" /usr/bin/tee "$remote_source" \
    < "$source_file" >/dev/null
"$MACVM_TART" exec -i "$MACVM_NAME" /usr/bin/tee "$remote_contents/Info.plist" \
    < "$info_file" >/dev/null
"$MACVM_TART" exec "$MACVM_NAME" /bin/mkdir -p \
    "$(/usr/bin/dirname "$remote_control_cli")"
"$MACVM_TART" exec -i "$MACVM_NAME" /usr/bin/tee "$remote_control_cli" \
    < "$control_cli_file" >/dev/null
"$MACVM_TART" exec "$MACVM_NAME" /usr/bin/xcrun swiftc -O \
    -framework AppKit -framework ApplicationServices -framework CoreGraphics \
    -framework SystemConfiguration \
    -o "$remote_binary" "$remote_source"
"$MACVM_TART" exec "$MACVM_NAME" /bin/chmod 755 "$remote_binary"
"$MACVM_TART" exec "$MACVM_NAME" /bin/chmod 755 "$remote_control_cli"
"$MACVM_TART" exec "$MACVM_NAME" /usr/bin/codesign --force --deep \
    --sign - --identifier com.kzahel.macvm-testbed.ui \
    --requirements '=designated => identifier "com.kzahel.macvm-testbed.ui"' \
    "$remote_app"

printf 'Deployed %s\n' "$remote_app"
"$MACVM_REPO_DIR/bin/macui" resident-start >/dev/null
"$MACVM_REPO_DIR/bin/macui" control '{"operation":"status"}'
