#!/usr/bin/env bash
# Assemble and ad-hoc sign Machine Control.app from the resident package.
# The same bundle serves VM guests and physical hosts; the root-owned
# deployment policy, not the build, decides what it may do.

set -euo pipefail

readonly PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly MACOS_DIR="$(cd "$PACKAGE_DIR/.." && pwd)"
readonly BUNDLE_ID='org.machine-control.app'

output="$PACKAGE_DIR/.build/app"
arch="$(/usr/bin/uname -m)"
while (( $# )); do
    case "$1" in
        --output) output="$2"; shift 2 ;;
        --arch) arch="$2"; shift 2 ;;
        -h|--help)
            printf 'Usage: build-app.sh [--output DIR] [--arch arm64|x86_64]\n'
            exit 0
            ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
    esac
done

app="$output/Machine Control.app"
contents="$app/Contents"
/bin/rm -rf "$app"
/bin/mkdir -p "$contents/MacOS" "$contents/Resources"

/usr/bin/xcrun swiftc -O -target "$arch-apple-macos13.0" \
    -framework AppKit -framework ApplicationServices -framework CoreGraphics \
    -framework SystemConfiguration -framework Carbon -framework ScreenCaptureKit -framework ServiceManagement \
    -o "$contents/MacOS/macui" "$PACKAGE_DIR"/Sources/macui/*.swift
/usr/bin/xcrun clang -O2 -target "$arch-apple-macos13.0" -fobjc-arc \
    -Wno-unused-function -framework Foundation -framework IOKit \
    -o "$contents/Resources/mc-session-probe" \
    "$MACOS_DIR/guests/macos/unlock/Probe.m"
/bin/cp "$PACKAGE_DIR/app/Info.plist" "$contents/Info.plist"
/bin/cp "$PACKAGE_DIR/app/org.machine-control.resident.plist.in" "$contents/Resources/"
/bin/cp -R "$PACKAGE_DIR/policies" "$contents/Resources/policies"
MC_UNLOCK_ARCH="$arch" "$MACOS_DIR/guests/macos/unlock/build.sh" "$contents/Resources/unlock" >/dev/null
/bin/mkdir -p "$contents/Library/LaunchDaemons"
/bin/cp "$MACOS_DIR/guests/macos/unlock/org.machine-control.unlock.plist" "$contents/Library/LaunchDaemons/"
# Development builds remember their checkout so setup can point at the
# unpacked Chrome extension.
/usr/bin/plutil -replace MCSourceCheckout -string "$(cd "$MACOS_DIR/../.." && pwd)" \
    "$contents/Info.plist"
/usr/bin/plutil -lint "$contents/Info.plist" >/dev/null

# Development builds are ad-hoc signed with a pinned identifier so macOS
# consent survives rebuilds. Release builds need a Developer ID requirement.
/usr/bin/codesign --force --deep --sign - --identifier "$BUNDLE_ID" \
    --requirements "=designated => identifier \"$BUNDLE_ID\"" "$app"
/usr/bin/codesign --verify --strict "$app"
printf '%s\n' "$app"
