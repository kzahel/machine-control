#!/usr/bin/env bash
set -euo pipefail

app="${1:?application bundle required}"
: "${MACOS_CERTIFICATE_P12_BASE64:?}"
: "${MACOS_CERTIFICATE_PASSWORD:?}"
: "${MACOS_KEYCHAIN_PASSWORD:?}"
: "${MACOS_SIGNING_IDENTITY:?}"
: "${APPLE_TEAM_ID:?}"
: "${ASC_API_KEY_P8_BASE64:?}"
: "${ASC_API_KEY_ID:?}"
: "${ASC_API_ISSUER_ID:?}"

umask 077
signing_temp="$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/mc-signing.XXXXXX")"
keychain="$signing_temp/signing.keychain-db"
security list-keychains -d user > "$signing_temp/search-list"
security default-keychain -d user > "$signing_temp/default-keychain"
cleanup() {
    python3 - "$signing_temp" <<'PY' || true
from pathlib import Path
import shlex
import subprocess
import sys
state = Path(sys.argv[1])
for name, command in (("search-list", "list-keychains"),
                      ("default-keychain", "default-keychain")):
    previous = shlex.split((state / name).read_text())
    subprocess.run(["security", command, "-d", "user", "-s", *previous],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
PY
    security delete-keychain "$keychain" >/dev/null 2>&1 || true
    rm -rf "$signing_temp"
}
trap cleanup EXIT

printf '%s' "$MACOS_CERTIFICATE_P12_BASE64" | base64 --decode > "$signing_temp/certificate.p12"
printf '%s' "$ASC_API_KEY_P8_BASE64" | base64 --decode > "$signing_temp/notary.p8"
security create-keychain -p "$MACOS_KEYCHAIN_PASSWORD" "$keychain"
security list-keychains -d user -s "$keychain"
security default-keychain -d user -s "$keychain"
security unlock-keychain -p "$MACOS_KEYCHAIN_PASSWORD" "$keychain"
security set-keychain-settings -t 3600 -u "$keychain"
security import "$signing_temp/certificate.p12" -k "$keychain" \
    -P "$MACOS_CERTIFICATE_PASSWORD" -T /usr/bin/codesign >/dev/null
security set-key-partition-list -S apple-tool:,apple:,codesign: \
    -s -k "$MACOS_KEYCHAIN_PASSWORD" "$keychain" >/dev/null
rm "$signing_temp/certificate.p12"
security find-identity -v -p codesigning "$keychain"

# Sign nested code before sealing the containing bundle.
codesign --force --timestamp --options runtime --keychain "$keychain" \
    --sign "$MACOS_SIGNING_IDENTITY" \
    "$app/Contents/Helpers/machine-control-smoke-helper"
codesign --force --timestamp --options runtime --keychain "$keychain" \
    --sign "$MACOS_SIGNING_IDENTITY" "$app"
codesign --verify --deep --strict "$app"
codesign --verify --strict \
    -R "anchor apple generic and certificate leaf[subject.OU] = \"$APPLE_TEAM_ID\"" "$app"

ditto -c -k --sequesterRsrc --keepParent "$app" "$signing_temp/notarize.zip"
xcrun notarytool submit "$signing_temp/notarize.zip" \
    --key "$signing_temp/notary.p8" --key-id "$ASC_API_KEY_ID" \
    --issuer "$ASC_API_ISSUER_ID" --wait --timeout 20m \
    --output-format json > "$signing_temp/notarization.json"
python3 - "$signing_temp/notarization.json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as stream:
    result = json.load(stream)
if result.get("status") != "Accepted":
    raise SystemExit("Notarization was not accepted: " + str(result.get("status")))
print("Notarization accepted")
PY
xcrun stapler staple "$app"
xcrun stapler validate "$app"
spctl --assess --type execute "$app"
codesign --verify --deep --strict "$app"
"$app/Contents/MacOS/machine-control-smoke"
"$app/Contents/Helpers/machine-control-smoke-helper"
