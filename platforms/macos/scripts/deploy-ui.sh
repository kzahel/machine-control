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

source_dir="$MACVM_REPO_DIR/resident/Sources/macui"
source_files=("$source_dir"/*.swift)
probe_source="$MACVM_REPO_DIR/guests/macos/unlock/Probe.m"
session_header="$MACVM_REPO_DIR/guests/macos/unlock/Session.h"
source_digest="$(
    for file in "${source_files[@]}"; do
        printf '%s\n' "$(/usr/bin/basename "$file")"
        /bin/cat "$file"
    done | /bin/cat - "$probe_source" "$session_header" |
        /usr/bin/shasum -a 256 | /usr/bin/awk '{print $1}'
)"
info_file="$MACVM_REPO_DIR/guests/macos/ui/Info.plist"
control_cli_file="$MACVM_REPO_DIR/guests/macos/ui/machine-control"
resident_plist_template="$MACVM_REPO_DIR/guests/macos/ui/com.kzahel.macvm-testbed.resident.plist.in"
remote_directory="$(macvm_remote_ui_dir)"
remote_source_dir="$remote_directory/src"
remote_source="$remote_source_dir/main.swift"
remote_app="$(macvm_remote_ui_app)"
remote_contents="$remote_app/Contents"
remote_binary="$(macvm_remote_ui_binary)"
remote_control_cli="$(macvm_remote_control_cli)"
remote_socket="$(macvm_remote_control_socket)"
remote_resident_plist="$(macvm_remote_resident_plist)"
remote_resident_log="$remote_directory/resident.log"

escape_sed_replacement() {
    printf '%s' "$1" | /usr/bin/sed -e 's/[\\&|]/\\&/g'
}

local_resident_plist="$(mktemp "${TMPDIR:-/tmp}/macvm-resident.XXXXXX")"
trap '/bin/rm -f -- "$local_resident_plist"' EXIT
/usr/bin/sed \
    -e "s|__MACVM_RESIDENT_BINARY__|$(escape_sed_replacement "$remote_binary")|g" \
    -e "s|__MACVM_RESIDENT_SOCKET__|$(escape_sed_replacement "$remote_socket")|g" \
    -e "s|__MACVM_RESIDENT_LOG__|$(escape_sed_replacement "$remote_resident_log")|g" \
    "$resident_plist_template" >"$local_resident_plist"
/usr/bin/plutil -lint "$local_resident_plist" >/dev/null

if ! macvm_exec /usr/bin/true; then
    printf 'Guest command transport is unavailable; read docs/bootstrap.md\n' >&2
    exit 1
fi

# The resident reads its deployment policy from a root-owned file and treats
# anything absent or untrusted as a personal workstation. Tart guests are
# disposable appliances, so install the standing policy before the resident.
policy_file="$MACVM_REPO_DIR/resident/policies/appliance.json"
remote_policy_dir='/Library/Application Support/MachineControl'
remote_policy="$remote_policy_dir/policy.json"
local_policy_hash="$(/usr/bin/shasum -a 256 "$policy_file" | /usr/bin/awk '{print $1}')"
remote_policy_hash="$(macvm_exec /usr/bin/shasum -a 256 "$remote_policy" 2>/dev/null |
    /usr/bin/awk '{print $1}' || true)"
policy_owner="$(macvm_exec /usr/bin/stat -f '%Su:%Sg:%Lp' "$remote_policy" 2>/dev/null || true)"
if [[ "$local_policy_hash" != "$remote_policy_hash" || "$policy_owner" != 'root:wheel:644' ]]; then
    macvm_exec /usr/bin/sudo -n /usr/bin/install -d -o root -g wheel -m 755 \
        "$remote_policy_dir"
    macvm_exec -i /usr/bin/sudo -n /usr/bin/tee "$remote_policy.new" \
        < "$policy_file" >/dev/null
    macvm_exec /usr/bin/sudo -n /usr/sbin/chown root:wheel "$remote_policy.new"
    macvm_exec /usr/bin/sudo -n /bin/chmod 644 "$remote_policy.new"
    macvm_exec /usr/bin/sudo -n /bin/mv -f "$remote_policy.new" "$remote_policy"
    printf 'Installed appliance deployment policy at %s\n' "$remote_policy"
    policy_changed=true
else
    policy_changed=false
fi

if ! macvm_exec /usr/bin/xcrun --find swiftc >/dev/null; then
    printf 'Guest Xcode Command Line Tools are required to compile macui\n' >&2
    exit 1
fi

binary_current=false
plist_current=false
if (( ! force )) &&
        macvm_exec /bin/test -x "$remote_binary" >/dev/null 2>&1 &&
        macvm_exec /bin/test -f "$remote_source" >/dev/null 2>&1 &&
        macvm_exec /bin/test -f "$remote_contents/Info.plist" \
            >/dev/null 2>&1; then
    local_source_hash="$source_digest"
    local_info_hash="$(/usr/bin/shasum -a 256 "$info_file" | /usr/bin/awk '{print $1}')"
    remote_source_hash="$(macvm_exec /bin/cat "$remote_directory/source-digest" 2>/dev/null || true)"
    remote_info_hash="$(
        macvm_exec /usr/bin/shasum -a 256 \
            "$remote_contents/Info.plist" | /usr/bin/awk '{print $1}'
    )"
    if [[ "$local_source_hash" == "$remote_source_hash" \
            && "$local_info_hash" == "$remote_info_hash" ]]; then
        binary_current=true
    fi
fi
if [[ "$binary_current" == true ]] &&
        macvm_exec /bin/test -f "$remote_resident_plist" \
            >/dev/null 2>&1; then
    local_plist_hash="$(/usr/bin/shasum -a 256 "$local_resident_plist" | \
        /usr/bin/awk '{print $1}')"
    remote_plist_hash="$(macvm_exec /usr/bin/shasum -a 256 \
        "$remote_resident_plist" | /usr/bin/awk '{print $1}')"
    if [[ "$local_plist_hash" == "$remote_plist_hash" ]]; then
        plist_current=true
    fi
fi
if [[ "$binary_current" == true && "$plist_current" == true ]]; then
    printf 'MacVM UI is already current at %s\n' "$remote_app"
    if [[ "$policy_changed" == true ]]; then
        "$MACVM_REPO_DIR/bin/macui" resident-stop >/dev/null 2>&1 || true
    fi
    "$MACVM_REPO_DIR/bin/macui" resident-start >/dev/null
    "$MACVM_REPO_DIR/bin/macui" control '{"operation":"status"}'
    exit 0
fi

if [[ "$binary_current" == true ]]; then
    "$MACVM_REPO_DIR/bin/macui" resident-stop >/dev/null 2>&1 || true
    macvm_exec /bin/mkdir -p \
        "$remote_directory" "$(/usr/bin/dirname "$remote_resident_plist")"
    macvm_exec -i /usr/bin/tee "$remote_resident_plist" \
        < "$local_resident_plist" >/dev/null
    macvm_exec /bin/chmod 600 "$remote_resident_plist"
    macvm_exec /usr/bin/plutil -lint "$remote_resident_plist" >/dev/null
    printf 'Installed resident LaunchAgent for current %s\n' "$remote_app"
    "$MACVM_REPO_DIR/bin/macui" resident-start >/dev/null
    "$MACVM_REPO_DIR/bin/macui" control '{"operation":"status"}'
    exit 0
fi

# A prior resident may still have the old executable mapped. Ask it to stop
# before replacement; an absent or older service is harmless here.
"$MACVM_REPO_DIR/bin/macui" resident-stop >/dev/null 2>&1 || true

macvm_exec /bin/mkdir -p \
    "$remote_directory" "$remote_contents/MacOS" "$remote_contents/Resources" \
    "$(/usr/bin/dirname "$remote_resident_plist")"
macvm_exec /bin/rm -rf "$remote_source_dir"
macvm_exec /bin/mkdir -p "$remote_source_dir"
remote_source_files=()
for file in "${source_files[@]}"; do
    remote_file="$remote_source_dir/$(/usr/bin/basename "$file")"
    macvm_exec -i /usr/bin/tee "$remote_file" < "$file" >/dev/null
    remote_source_files+=("$remote_file")
done
macvm_exec -i /usr/bin/tee "$remote_contents/Info.plist" \
    < "$info_file" >/dev/null
macvm_exec /bin/mkdir -p \
    "$(/usr/bin/dirname "$remote_control_cli")"
macvm_exec -i /usr/bin/tee "$remote_control_cli" \
    < "$control_cli_file" >/dev/null
macvm_exec -i /usr/bin/tee "$remote_resident_plist" \
    < "$local_resident_plist" >/dev/null
macvm_exec -i /usr/bin/tee "$remote_directory/Probe.m" < "$probe_source" >/dev/null
macvm_exec -i /usr/bin/tee "$remote_directory/Session.h" < "$session_header" >/dev/null
macvm_guest_xcrun clang -fobjc-arc -Wno-unused-function \
    -framework Foundation -framework IOKit -o "$remote_contents/Resources/mc-session-probe" \
    "$remote_directory/Probe.m"
macvm_guest_xcrun swiftc -O \
    -framework AppKit -framework ApplicationServices -framework CoreGraphics \
    -framework SystemConfiguration \
    -o "$remote_binary" "${remote_source_files[@]}"
macvm_exec /bin/chmod 755 "$remote_binary"
macvm_exec /bin/chmod 755 "$remote_control_cli"
macvm_exec /bin/chmod 600 "$remote_resident_plist"
macvm_exec /usr/bin/plutil -lint "$remote_resident_plist" >/dev/null
macvm_exec /usr/bin/codesign --force --deep \
    --sign - --identifier com.kzahel.macvm-testbed.ui \
    --requirements '=designated => identifier "com.kzahel.macvm-testbed.ui"' \
    "$remote_app"

printf '%s\n' "$source_digest" | macvm_exec -i /usr/bin/tee "$remote_directory/source-digest" >/dev/null
printf 'Deployed %s\n' "$remote_app"
"$MACVM_REPO_DIR/bin/macui" resident-start >/dev/null
"$MACVM_REPO_DIR/bin/macui" control '{"operation":"status"}'
