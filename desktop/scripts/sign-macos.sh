#!/usr/bin/env bash
# Sign the actual Tauri bundle after assembly. CI imports its keychain;
# a local run may use an existing Developer ID identity in the login keychain.
set -euo pipefail
app="${1:?app bundle required}"
: "${MACOS_SIGNING_IDENTITY:?}"
: "${APPLE_TEAM_ID:?}"
: "${APPLE_API_KEY_PATH:?}"
: "${ASC_API_KEY_ID:?}"
: "${ASC_API_ISSUER_ID:?}"
output="${2:?output directory required}"
mkdir -p "$output"
output="$(cd "$output" && pwd)"
work="$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/mc-desktop-notary.XXXXXX")"
trap 'python3 -c "import shutil,sys; shutil.rmtree(sys.argv[1])" "$work"' EXIT
codesign --force --timestamp --options runtime --sign "$MACOS_SIGNING_IDENTITY" \
    "$app/Contents/Frameworks/MCResident.framework"
codesign --force --timestamp --options runtime --sign "$MACOS_SIGNING_IDENTITY" \
    "$app/Contents/Resources/mc-session-probe"
codesign --force --timestamp --options runtime --sign "$MACOS_SIGNING_IDENTITY" \
    --identifier org.machine-control.sudo "$app/Contents/Resources/mc-sudo"
codesign --force --timestamp --options runtime --sign "$MACOS_SIGNING_IDENTITY" \
    --identifier org.machine-control.sudo.askpass "$app/Contents/Resources/mc-sudo-askpass"
# Standalone CPython and its extension libraries are nested native code. Sign
# each Mach-O before sealing the scripts and byte inventory in the app bundle.
python3 - "$app/Contents/Resources/mc-cli" <<'PY'
import os, pathlib, subprocess, sys
root = pathlib.Path(sys.argv[1])
for path in sorted(root.rglob('*')):
    if not path.is_file():
        continue
    with path.open('rb') as stream:
        magic = stream.read(4)
    if magic in {b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'}:
        subprocess.run(['codesign', '--force', '--timestamp', '--options', 'runtime',
                        '--sign', os.environ['MACOS_SIGNING_IDENTITY'], str(path)], check=True)
PY
python3 desktop/scripts/cli-payload.py inventory "$app/Contents/Resources/mc-cli"
codesign --force --timestamp --options runtime --sign "$MACOS_SIGNING_IDENTITY" "$app"
codesign --verify --deep --strict "$app"
codesign --verify --strict -R "=anchor apple generic and certificate leaf[subject.OU] = \"$APPLE_TEAM_ID\" and identifier \"org.machine-control.app\"" "$app"
ditto -c -k --sequesterRsrc --keepParent "$app" "$work/notarize.zip"
xcrun notarytool submit "$work/notarize.zip" --key "$APPLE_API_KEY_PATH" \
    --key-id "$ASC_API_KEY_ID" --issuer "$ASC_API_ISSUER_ID" --wait --timeout 20m \
    --output-format json > "$output/notarization.json"
python3 - "$output/notarization.json" <<'PY'
import json,sys
if json.load(open(sys.argv[1]))['status'] != 'Accepted':
    raise SystemExit('Notarization did not accept this bundle')
PY
xcrun stapler staple "$app"
xcrun stapler validate "$app"
spctl --assess --type execute "$app"
version="$(/usr/libexec/PlistBuddy -c 'Print CFBundleShortVersionString' "$app/Contents/Info.plist")"
arch="$(lipo -archs "$app/Contents/MacOS/macui")"
archive="$output/MachineControl_${version}_${arch}.app.tar.gz"
COPYFILE_DISABLE=1 tar -czf "$archive" -C "$(dirname "$app")" "$(basename "$app")"
# Sign final, stapled bytes; the signature also authenticates the version.
(cd desktop && pnpm exec tauri signer sign --app-version "$version" "$archive")
mkdir -p "$work/dmg"
ditto "$app" "$work/dmg/Machine Control.app"
ln -s /Applications "$work/dmg/Applications"
dmg="$output/MachineControl_${version}_${arch}.dmg"
hdiutil create -volname 'Machine Control' -srcfolder "$work/dmg" -ov -format UDZO "$dmg" >/dev/null
codesign --timestamp --sign "$MACOS_SIGNING_IDENTITY" "$dmg"
xcrun notarytool submit "$dmg" --key "$APPLE_API_KEY_PATH" --key-id "$ASC_API_KEY_ID" \
    --issuer "$ASC_API_ISSUER_ID" --wait --timeout 20m --output-format json > "$output/dmg-notarization.json"
python3 - "$output/dmg-notarization.json" <<'PY'
import json,sys
if json.load(open(sys.argv[1]))['status'] != 'Accepted': raise SystemExit('DMG notarization failed')
PY
xcrun stapler staple "$dmg"
xcrun stapler validate "$dmg"
codesign --verify --deep --strict "$app"
python3 desktop/scripts/package-evidence.py "$app" "$output"
