#!/bin/bash
# Run over the claimed guest SSH session after the caller stages a pinned DMG.
set -euo pipefail
umask 077

stage="$1"
expected="$2"
[[ "$stage" =~ ^/tmp/machine-control-package\.[A-Za-z0-9]+$ ]]
[[ "$expected" =~ ^[0-9a-f]{64}$ ]]
digest="$(/usr/bin/shasum -a 256 "$stage/package.dmg" | /usr/bin/awk '{print $1}')"
[[ "$digest" == "$expected" ]] || { printf 'Guest package digest mismatch\n' >&2; exit 1; }

mount="$stage/mount"
mkdir "$mount"
incoming=
cleanup() {
    /usr/bin/hdiutil detach "$mount" >/dev/null 2>&1 || true
    if [[ -n "$incoming" ]]; then
        if [[ -e "$incoming/Machine Control.app" ]]; then
            /bin/rm -R "$incoming/Machine Control.app" || true
        fi
        /bin/rmdir "$incoming" 2>/dev/null || true
    fi
}
trap cleanup EXIT
/usr/bin/hdiutil attach "$stage/package.dmg" -nobrowse -readonly -mountpoint "$mount" >/dev/null

source_app="$mount/Machine Control.app"
app="/Applications/Machine Control.app"
verify() {
    /usr/bin/file -b "$1/Contents/MacOS/macui" | /usr/bin/grep -q 'Mach-O 64-bit executable x86_64'
    /usr/bin/codesign --verify --deep --strict "$1"
    /usr/bin/codesign --verify --strict \
        -R '=anchor apple generic and certificate leaf[field.1.2.840.113635.100.6.1.13] exists' "$1"
}
code_hash() {
    /usr/bin/codesign -dv --verbose=4 "$1" 2>&1 | /usr/bin/sed -n 's/^CDHash=//p'
}
verify "$source_app"
/usr/sbin/spctl --assess --type execute "$source_app"
expected_code="$(code_hash "$source_app")"
[[ -n "$expected_code" ]]

if [[ ! -e "$app" && ! -L "$app" ]]; then
    incoming="$(mktemp -d /Applications/.machine-control-install.XXXXXXXX)"
    /usr/bin/ditto "$source_app" "$incoming/Machine Control.app"
    verify "$incoming/Machine Control.app"
    /bin/mv -n "$incoming/Machine Control.app" "$app"
fi
verify "$app"
[[ "$(code_hash "$app")" == "$expected_code" ]] || {
    printf 'Installed Machine Control differs from the verified package\n' >&2
    exit 1
}
/usr/bin/defaults read "$app/Contents/Info" CFBundleShortVersionString
