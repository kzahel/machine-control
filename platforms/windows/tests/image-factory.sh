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
    arm64 fixture 1 windows-11-pro "$secret" "$public_key" \
    "$guest_tools_iso" >/dev/null
test -f "$temporary/output/winvm-seed.iso"
test -f "$temporary/output/winvm-boot.img"
seed_mount="$temporary/seed-mount"
mkdir "$seed_mount"
hdiutil attach -readonly -nobrowse -mountpoint "$seed_mount" \
    "$temporary/output/winvm-seed.iso" >/dev/null
test -f "$seed_mount/utm-guest-tools-fixture.exe"
test -f "$seed_mount/Drivers/NetKVM/w11/ARM64/netkvm.inf"
grep -Fq 'FS1:\EFI\Microsoft\Boot\bootmgfw.efi' \
    "$seed_mount/startup.nsh"
grep -Fq 'FS2:\EFI\Microsoft\Boot\bootmgfw.efi' \
    "$seed_mount/startup.nsh"
grep -Fq 'FS9:\EFI\Microsoft\Boot\bootmgfw.efi' \
    "$seed_mount/startup.nsh"
grep -Fq '<WillShowUI>Never</WillShowUI>' \
    "$seed_mount/Autounattend.xml"
grep -Fq '<Key>W269N-WFGWX-YVC9B-4J6C9-T83GX</Key>' \
    "$seed_mount/Autounattend.xml"
grep -Fq 'E:\Drivers\NetKVM\w11\ARM64' "$seed_mount/Autounattend.xml"
grep -Fq 'Microsoft-Windows-PnpCustomizationsNonWinPE' \
    "$seed_mount/Autounattend.xml"
[[ "$(grep -Fc 'E:\Drivers\NetKVM\w11\ARM64' \
    "$seed_mount/Autounattend.xml")" == '2' ]]
grep -Fq '<SkipAutoActivation>true</SkipAutoActivation>' \
    "$seed_mount/Autounattend.xml"
grep -Fq '<HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE>' \
    "$seed_mount/Autounattend.xml"
grep -Fq 'BypassTPMCheck' "$seed_mount/Autounattend.xml"
hdiutil detach "$seed_mount" >/dev/null
boot_mount="$temporary/boot-mount"
mkdir "$boot_mount"
[[ "$(hdiutil pmap "$temporary/output/winvm-boot.img")" == \
    *'scheme:     none'* ]]
hdiutil attach -readonly -nobrowse -mountpoint "$boot_mount" \
    "$temporary/output/winvm-boot.img" >/dev/null
grep -Fq 'FS0:\EFI\BOOT\BOOTAA64.EFI' "$boot_mount/startup.nsh"
hdiutil detach "$boot_mount" >/dev/null

installer_source="$temporary/installer-source"
installer_boot="$temporary/installer-boot"
installer_boot_image="$temporary/installer-boot.img"
mkdir -p "$installer_source/efi/microsoft/boot" \
    "$installer_boot/EFI/BOOT"
printf 'prompted-loader' > \
    "$installer_source/efi/microsoft/boot/cdboot.efi"
printf 'noprompt-loader' > \
    "$installer_source/efi/microsoft/boot/cdboot_noprompt.efi"
cp "$installer_source/efi/microsoft/boot/cdboot.efi" \
    "$installer_boot/EFI/BOOT/BOOTAA64.EFI"
hdiutil create -quiet -size 2m -fs 'MS-DOS FAT12' -layout NONE \
    -type UDTO -volname EFISECTOR "$temporary/installer-boot-volume"
installer_boot_mount="$temporary/installer-boot-mount"
mkdir "$installer_boot_mount"
hdiutil attach -nobrowse -mountpoint "$installer_boot_mount" \
    "$temporary/installer-boot-volume.cdr" >/dev/null
mkdir -p "$installer_boot_mount/EFI/BOOT"
cp "$installer_boot/EFI/BOOT/BOOTAA64.EFI" \
    "$installer_boot_mount/EFI/BOOT/BOOTAA64.EFI"
hdiutil detach "$installer_boot_mount" >/dev/null
mv "$temporary/installer-boot-volume.cdr" "$installer_boot_image"
installer_iso="$temporary/windows-fixture.iso"
hdiutil makehybrid -quiet -iso -joliet \
    -o "$installer_iso" "$installer_source"
perl - "$installer_iso" "$installer_boot_image" <<'PERL'
use strict;
use warnings;
my ($iso, $boot_path) = @ARGV;
open my $boot_fh, '<:raw', $boot_path or die "open boot fixture: $!\n";
local $/;
my $boot = <$boot_fh>;
length($boot) % 512 == 0 or die "unaligned boot fixture\n";
open my $iso_fh, '+<:raw', $iso or die "open ISO fixture: $!\n";
my $size = -s $iso;
my $catalog_lba = int(($size + 2047) / 2048) + 1;
my $boot_lba = $catalog_lba + 1;
my $descriptor = pack('C', 0) . 'CD001' . pack('C', 1) .
    "EL TORITO SPECIFICATION";
$descriptor .= "\0" x (71 - length($descriptor));
$descriptor .= pack('V', $catalog_lba);
$descriptor .= "\0" x (2048 - length($descriptor));
seek $iso_fh, 17 * 2048, 0 or die "seek descriptor fixture: $!\n";
print {$iso_fh} $descriptor;
my $validation = pack('CCv', 1, 0xef, 0) . ("\0" x 24) .
    pack('v', 0) . "\x55\xaa";
my $entry = pack('CCvCCvV', 0x88, 0, 0, 0, 0,
    length($boot) / 512, $boot_lba) . ("\0" x 20);
my $catalog = $validation . $entry;
$catalog .= "\0" x (2048 - length($catalog));
seek $iso_fh, $catalog_lba * 2048, 0 or die "seek catalog fixture: $!\n";
print {$iso_fh} $catalog;
seek $iso_fh, $boot_lba * 2048, 0 or die "seek boot fixture: $!\n";
print {$iso_fh} $boot;
PERL
source_digest="$(shasum -a 256 "$installer_iso" | awk '{print $1}')"
WINVM_FACTORY_LOCAL_ROOT="$temporary/prepared" \
    "$REPO_DIR/scripts/image-factory.sh" prepare-install-media \
    "$installer_iso" >/dev/null
prepared_iso="$temporary/prepared/windows-install-noprompt.iso"
test -f "$prepared_iso"
[[ "$(shasum -a 256 "$installer_iso" | awk '{print $1}')" == \
    "$source_digest" ]]
[[ "$(shasum -a 256 "$prepared_iso" | awk '{print $1}')" != \
    "$source_digest" ]]
if WINVM_FACTORY_LOCAL_ROOT="$temporary/prepared" \
    "$REPO_DIR/scripts/image-factory.sh" prepare-install-media \
    "$installer_iso" >/dev/null 2>&1; then
    printf 'Existing prepared media was unexpectedly overwritten.\n' >&2
    exit 1
fi

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
    arm64 fixture 1 windows-11-pro "$secret" "$public_key" \
    "$guest_tools_iso" \
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
