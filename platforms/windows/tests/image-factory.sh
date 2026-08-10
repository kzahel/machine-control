#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary="$(mktemp -d /tmp/winvm-image-factory-test.XXXXXX)"
trap 'rm -rf -- "$temporary"' EXIT
secret="$temporary/secret"
public_key="$temporary/controller.pub"
guest_tools_staging="$temporary/guest-tools"
guest_tools_iso="$temporary/utm-guest-tools.iso"
printf 'fixture&ampersand!42\n' > "$secret"
chmod 600 "$secret"
printf 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFixtureOnly factory@test\n' > \
    "$public_key"
mkdir -p "$guest_tools_staging/Drivers/NetKVM/w11/ARM64"
printf 'fixture driver\n' > \
    "$guest_tools_staging/Drivers/NetKVM/w11/ARM64/netkvm.inf"
printf 'fixture installer\n' > \
    "$guest_tools_staging/utm-guest-tools-fixture.exe"
hdiutil makehybrid -quiet -iso -joliet \
    -default-volume-name 'UTM Guest Tools' -o "$guest_tools_iso" \
    "$guest_tools_staging"

WINVM_FACTORY_LOCAL_ROOT="$temporary/output" \
    "$REPO_DIR/scripts/image-factory.sh" render-seed \
    arm64 fixture 1 "$secret" "$public_key" "$guest_tools_iso" >/dev/null
test -f "$temporary/output/winvm-seed.iso"
hdiutil pmap "$temporary/output/winvm-seed.iso" >/dev/null
seed_mount="$temporary/seed-mount"
mkdir "$seed_mount"
hdiutil attach -readonly -nobrowse -mountpoint "$seed_mount" \
    "$temporary/output/winvm-seed.iso" >/dev/null
test -f "$seed_mount/utm-guest-tools-fixture.exe"
test -f "$seed_mount/Drivers/NetKVM/w11/ARM64/netkvm.inf"
grep -Fq 'E:\Drivers\NetKVM\w11\ARM64' "$seed_mount/Autounattend.xml"
grep -Fq '<SkipAutoActivation>true</SkipAutoActivation>' \
    "$seed_mount/Autounattend.xml"
grep -Fq 'BypassTPMCheck' "$seed_mount/Autounattend.xml"
hdiutil detach "$seed_mount" >/dev/null

bundle="$temporary/fixture.utm"
mkdir -p "$bundle/Data"
plutil -create xml1 "$bundle/config.plist"
plutil -insert Backend -string QEMU "$bundle/config.plist"
plutil -insert System -xml '<dict><key>Architecture</key><string>aarch64</string></dict>' \
    "$bundle/config.plist"
plutil -insert Drive -xml '<array><dict><key>ImageType</key><string>Disk</string></dict></array>' \
    "$bundle/config.plist"
printf 'fixture disk\n' > "$bundle/Data/disk.qcow2"
"$REPO_DIR/scripts/image-manifest.sh" "$bundle" --oobe-confirmed >/dev/null
manifest="$temporary/fixture.manifest.json"
[[ "$(jq -r '.schema' "$manifest")" == 'winvm-image-manifest/v0' ]]
[[ "$(jq -r '.verification.disposable_oobe_confirmed' "$manifest")" == 'true' ]]
[[ "$(jq -r '.architecture' "$manifest")" == 'aarch64' ]]
[[ "$(jq -r '.disk_count' "$manifest")" == '1' ]]

chmod 644 "$secret"
if WINVM_FACTORY_LOCAL_ROOT="$temporary/wrong-mode" \
    "$REPO_DIR/scripts/image-factory.sh" render-seed \
    arm64 fixture 1 "$secret" "$public_key" "$guest_tools_iso" \
    >/dev/null 2>&1; then
    printf 'World-readable secret file unexpectedly produced answer media.\n' >&2
    exit 1
fi

if "$REPO_DIR/scripts/image-factory.sh" validate-media \
    "$temporary/missing.iso" >/dev/null 2>&1; then
    printf 'Missing installation media unexpectedly validated.\n' >&2
    exit 1
fi

printf 'Image-factory tests passed.\n'
