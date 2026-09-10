#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd "$(dirname "$0")" && pwd)"
output="${1:?Usage: build.sh OUTPUT_DIRECTORY}"
mkdir -p "$output"
output="$(cd "$output" && pwd)"
flags=(-fobjc-arc -Wall -Wextra -Werror -Wno-unused-function)
frameworks=(-framework Foundation -framework Security -framework IOKit)
xcrun clang "${flags[@]}" "$source_dir/Probe.m" "${frameworks[@]}" -o "$output/mc-session-probe"
if [[ "${2:-}" == --probe-only ]]; then exit 0; fi
bundle="$output/MCUnlock.bundle"
mkdir -p "$bundle/Contents/MacOS"
xcrun clang "${flags[@]}" -bundle "$source_dir/Plugin.m" "${frameworks[@]}" -o "$bundle/Contents/MacOS/MCUnlock"
xcrun clang "${flags[@]}" "$source_dir/Broker.m" "${frameworks[@]}" -o "$output/mc-unlock-broker"
xcrun swiftc -O "$source_dir/Installer.swift" -o "$output/mc-unlock-install"
cat > "$bundle/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>org.machine-control.unlock-plugin</string>
<key>CFBundleExecutable</key><string>MCUnlock</string>
<key>CFBundleName</key><string>MCUnlock</string>
<key>CFBundlePackageType</key><string>BNDL</string>
<key>CFBundleVersion</key><string>1</string>
</dict></plist>
PLIST
for artifact in "$bundle" "$output/mc-unlock-broker" "$output/mc-unlock-install" "$output/mc-session-probe"; do
    codesign --force --sign "${MC_UNLOCK_SIGN_IDENTITY:--}" "$artifact"
done
