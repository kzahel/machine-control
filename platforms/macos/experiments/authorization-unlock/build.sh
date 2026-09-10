#!/usr/bin/env bash
set -euo pipefail

# Build only: no system installation, policy edit, or credential operation.
source_dir="$(cd "$(dirname "$0")" && pwd)"
output="${1:?Usage: build.sh OUTPUT_DIRECTORY}"
mkdir -p "$output"
output="$(cd "$output" && pwd)"
bundle="$output/MCUnlockExperiment.bundle"
mkdir -p "$bundle/Contents/MacOS"
flags=(-fobjc-arc -Wall -Wextra -Werror -Wno-unused-function)
frameworks=(-framework Foundation -framework Security -framework IOKit)
xcrun clang "${flags[@]}" -bundle "$source_dir/Plugin.m" \
    "${frameworks[@]}" -o "$bundle/Contents/MacOS/MCUnlockExperiment"
xcrun clang "${flags[@]}" "$source_dir/Control.m" \
    "${frameworks[@]}" -o "$output/mc-unlock-experiment"
/usr/bin/python3 - "$bundle/Contents/Info.plist" <<'PY'
import plistlib
import sys
with open(sys.argv[1], 'wb') as stream:
    plistlib.dump({
        'CFBundleIdentifier': 'org.machine-control.experiment.unlock-plugin',
        'CFBundleExecutable': 'MCUnlockExperiment',
        'CFBundleName': 'MCUnlockExperiment',
        'CFBundlePackageType': 'BNDL',
        'CFBundleVersion': '1',
    }, stream)
PY
codesign --force --sign - "$bundle"
printf 'Built authorization experiment in %s\n' "$output"
