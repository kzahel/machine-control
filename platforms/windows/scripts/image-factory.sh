#!/usr/bin/env bash

set -euo pipefail
# Keep parameter replacement literal across Bash 3.2 and Bash 5.2+.
shopt -u patsub_replacement 2>/dev/null || true

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly FACTORY_ROOT="${WINVM_FACTORY_LOCAL_ROOT:-$WINVM_REPO_DIR/.factory.local}"
readonly TEMPLATE="$WINVM_REPO_DIR/guests/windows/image-factory/Autounattend.xml.in"

usage() {
    cat <<'EOF'
Usage:
  image-factory.sh validate-media WINDOWS_ISO
  image-factory.sh prepare-install-media WINDOWS_ISO
  image-factory.sh render-seed ARCH USERNAME IMAGE_INDEX EDITION SECRET_FILE PUBLIC_KEY GUEST_TOOLS_ISO

Prepared installation media and the rendered seed are written under ignored
.factory.local. Preparation preserves the source ISO and replaces only the
verified prompted loader in a private copy with Microsoft's equal-size
no-prompt loader from that same ISO. SECRET_FILE must be mode 0600, contain one
non-empty line, and is never accepted as an argument or environment value.
EDITION is currently windows-11-pro and selects Microsoft's public
installation-only KMS client setup key; it does not activate Windows.
GUEST_TOOLS_ISO must be UTM Windows Guest Tools media. Its drivers and
installer are copied into the private seed so Windows Setup sees one
authoritative Autounattend.xml. The output contains plaintext setup credentials
and must be detached and securely discarded after bootstrap.
EOF
}

xml_escape() {
    local value="$1"
    # Backslash entity ampersands so this remains correct even if a caller
    # enables `patsub_replacement` after startup.
    value="${value//&/\&amp;}"
    value="${value//</\&lt;}"
    value="${value//>/\&gt;}"
    value="${value//\"/\&quot;}"
    value="${value//\'/\&apos;}"
    printf '%s' "$value"
}

validate_media() {
    if [[ $# -ne 1 || ! -f "$1" || ! -r "$1" ]]; then
        printf 'Windows installation media is absent or unreadable.\n' >&2
        return 1
    fi
    local size
    size="$(stat -f %z "$1" 2>/dev/null || stat -c %s "$1")"
    if [[ "$size" -lt 1073741824 ]]; then
        printf 'Windows installation media is unexpectedly small.\n' >&2
        return 1
    fi
    if command -v hdiutil >/dev/null 2>&1; then
        # `imageinfo` reports an internal error for valid raw ISO9660 images
        # on some macOS releases. `pmap` still validates the partition map.
        hdiutil pmap "$1" >/dev/null
    fi
    printf 'installation media validated\n'
}

prepare_install_media() (
    if [[ $# -ne 1 || ! -f "$1" || ! -r "$1" ]]; then
        printf 'Windows installation media is absent or unreadable.\n' >&2
        return 1
    fi
    for command_name in hdiutil perl cp; do
        if ! command -v "$command_name" >/dev/null 2>&1; then
            printf 'Required command not found: %s\n' "$command_name" >&2
            return 1
        fi
    done
    mkdir -p "$FACTORY_ROOT"
    chmod 700 "$FACTORY_ROOT"
    local source_iso output build mount source_device="" complete=0
    source_iso="$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")"
    output="$FACTORY_ROOT/windows-install-noprompt.iso"
    if [[ -e "$output" ]]; then
        printf 'Prepared installation media already exists; remove it explicitly.\n' >&2
        return 1
    fi
    build="$(mktemp -d "$FACTORY_ROOT/.install-media.XXXXXX")"
    mount="$build/source"
    mkdir "$mount"
    cleanup_install_media() {
        if [[ -n "$source_device" ]]; then
            hdiutil detach "$source_device" >/dev/null 2>&1 || true
        fi
        rm -rf -- "$build"
        if [[ "$complete" != "1" && -e "$output" ]]; then
            rm -f -- "$output"
        fi
    }
    trap cleanup_install_media EXIT
    if ! cp -c "$source_iso" "$output" 2>/dev/null; then
        cp "$source_iso" "$output"
    fi
    source_device="$(hdiutil attach -readonly -nobrowse \
        -mountpoint "$mount" "$source_iso" | \
        awk 'NF { device=$1 } END { print device }')"
    if [[ -z "$source_device" ]]; then
        printf 'Windows media did not expose an attached device.\n' >&2
        return 1
    fi
    local prompted="$mount/efi/microsoft/boot/cdboot.efi"
    local no_prompt="$mount/efi/microsoft/boot/cdboot_noprompt.efi"
    if [[ ! -f "$prompted" || ! -f "$no_prompt" ]]; then
        printf 'Windows media lacks the expected ARM64 CD boot loaders.\n' >&2
        return 1
    fi
    perl - "$source_iso" "$output" "$prompted" "$no_prompt" <<'PERL'
use strict;
use warnings;

my ($source, $output, $prompted_path, $no_prompt_path) = @ARGV;
open my $source_fh, '<:raw', $source or die "open source ISO: $!\n";
my $catalog_lba;
for my $sector (16 .. 63) {
    seek $source_fh, $sector * 2048, 0 or die "seek volume descriptor: $!\n";
    read($source_fh, my $descriptor, 2048) == 2048
        or die "read volume descriptor\n";
    if (ord(substr($descriptor, 0, 1)) == 0 &&
        substr($descriptor, 1, 5) eq 'CD001' &&
        substr($descriptor, 7, 23) eq "EL TORITO SPECIFICATION") {
        $catalog_lba = unpack('V', substr($descriptor, 71, 4));
        last;
    }
}
defined $catalog_lba or die "El Torito boot record not found\n";
seek $source_fh, $catalog_lba * 2048, 0 or die "seek boot catalog: $!\n";
read($source_fh, my $catalog, 2048) == 2048 or die "read boot catalog\n";
ord(substr($catalog, 30, 1)) == 0x55 && ord(substr($catalog, 31, 1)) == 0xaa
    or die "invalid El Torito validation entry\n";
my $entry;
for (my $offset = 32; $offset + 32 <= length($catalog); $offset += 32) {
    my $candidate = substr($catalog, $offset, 32);
    if (ord(substr($candidate, 0, 1)) == 0x88) {
        $entry = $candidate;
        last;
    }
}
defined $entry or die "bootable El Torito entry not found\n";
my $sector_count = unpack('v', substr($entry, 6, 2));
my $image_lba = unpack('V', substr($entry, 8, 4));
$sector_count > 0 && $image_lba > 0 or die "invalid boot image extent\n";
seek $source_fh, $image_lba * 2048, 0 or die "seek boot image: $!\n";
read($source_fh, my $boot_image, $sector_count * 512) == $sector_count * 512
    or die "read boot image\n";

sub read_file {
    my ($path) = @_;
    open my $fh, '<:raw', $path or die "open loader: $!\n";
    local $/;
    return <$fh>;
}
my $prompted = read_file($prompted_path);
my $no_prompt = read_file($no_prompt_path);
length($prompted) == length($no_prompt) && length($prompted) > 0
    or die "Windows boot-loader sizes differ\n";
my $loader_offset = index($boot_image, $prompted);
$loader_offset >= 0 or die "prompted loader not found in boot image\n";
index($boot_image, $prompted, $loader_offset + 1) < 0
    or die "prompted loader is not unique in boot image\n";

open my $output_fh, '+<:raw', $output or die "open output ISO: $!\n";
my $patch_offset = $image_lba * 2048 + $loader_offset;
seek $output_fh, $patch_offset, 0 or die "seek output loader: $!\n";
print {$output_fh} $no_prompt or die "write no-prompt loader: $!\n";
seek $output_fh, $patch_offset, 0 or die "verify output loader seek: $!\n";
read($output_fh, my $verified, length($no_prompt)) == length($no_prompt)
    or die "verify output loader read\n";
$verified eq $no_prompt or die "output loader verification failed\n";
PERL
    hdiutil detach "$source_device" >/dev/null
    source_device=""
    chmod 600 "$output"
    complete=1
    printf 'private no-prompt installation media prepared\n'
)

render_seed() {
    if [[ $# -ne 7 ]]; then usage >&2; return 2; fi
    local architecture="$1" username="$2" image_index="$3" edition="$4"
    local secret_file="$5" public_key="$6" guest_tools_iso="$7"
    case "$architecture" in arm64|amd64) ;; *) usage >&2; return 2 ;; esac
    if [[ ! "$username" =~ ^[A-Za-z][A-Za-z0-9_.-]{0,31}$ ||
        ! "$image_index" =~ ^[1-9][0-9]*$ ]]; then
        printf 'Username or image index is invalid.\n' >&2
        return 2
    fi
    local installation_key
    case "$edition" in
        windows-11-pro)
            # Microsoft's public Windows Pro KMS client setup key selects the
            # edition but cannot activate it without a separately configured
            # KMS host. The factory never accepts a customer activation key.
            installation_key='W269N-WFGWX-YVC9B-4J6C9-T83GX'
            ;;
        *)
            printf 'Unsupported unattended installation edition.\n' >&2
            return 2
            ;;
    esac
    if [[ ! -f "$secret_file" || ! -r "$secret_file" ||
        ! -f "$public_key" || ! -r "$public_key" ||
        ! -f "$guest_tools_iso" || ! -r "$guest_tools_iso" ]]; then
        printf 'Secret, public key, or guest-tools media is absent.\n' >&2
        return 1
    fi
    local mode
    mode="$(stat -f %Lp "$secret_file" 2>/dev/null || stat -c %a "$secret_file")"
    if [[ "$mode" != "600" ]]; then
        printf 'Secret file must have mode 0600.\n' >&2
        return 1
    fi
    local password
    password="$(<"$secret_file")"
    if [[ -z "$password" || ${#password} -gt 128 ||
        "$password" == *$'\n'* || "$password" == *$'\r'* ]]; then
        printf 'Secret file must contain one non-empty line of at most 128 characters.\n' >&2
        return 1
    fi
    local escaped_user escaped_password language="en-US"
    local driver_architecture
    if [[ "$architecture" == "arm64" ]]; then
        driver_architecture="ARM64"
    else
        driver_architecture="amd64"
    fi
    escaped_user="$(xml_escape "$username")"
    escaped_password="$(xml_escape "$password")"
    # The escaped values become replacement strings in the template
    # substitutions below, so protect their literal entity ampersands too.
    escaped_user="${escaped_user//&/\&}"
    escaped_password="${escaped_password//&/\&}"
    mkdir -p "$FACTORY_ROOT"
    chmod 700 "$FACTORY_ROOT"
    local staging media_build="" media_mount="" media_attached=0
    staging="$(mktemp -d "$FACTORY_ROOT/.seed.XXXXXX")"
    local tools_mount="$staging/guest-tools" tools_attached=0
    cleanup_seed_render() {
        if [[ "$media_attached" == "1" ]]; then
            hdiutil detach "$media_mount" >/dev/null 2>&1 || true
        fi
        if [[ "$tools_attached" == "1" ]]; then
            hdiutil detach "$tools_mount" >/dev/null 2>&1 || true
        fi
        rm -rf -- "$staging"
        if [[ -n "$media_build" ]]; then
            rm -rf -- "$media_build"
        fi
    }
    trap cleanup_seed_render RETURN
    mkdir -p "$tools_mount"
    hdiutil attach -readonly -nobrowse -mountpoint "$tools_mount" \
        "$guest_tools_iso" >/dev/null
    tools_attached=1
    local installers=("$tools_mount"/utm-guest-tools-*.exe)
    if [[ ! -d "$tools_mount/Drivers" || ${#installers[@]} -ne 1 ||
        ! -f "${installers[0]}" ]]; then
        printf 'Guest-tools media lacks Drivers or one UTM installer.\n' >&2
        return 1
    fi
    cp -R "$tools_mount/Drivers" "$staging/Drivers"
    chmod -R u+w "$staging/Drivers"
    cp "${installers[0]}" "$staging/"
    hdiutil detach "$tools_mount" >/dev/null
    tools_attached=0
    rmdir "$tools_mount"
    local content
    content="$(<"$TEMPLATE")"
    content="${content//__ARCHITECTURE__/$architecture}"
    content="${content//__DRIVER_ARCHITECTURE__/$driver_architecture}"
    content="${content//__LANGUAGE__/$language}"
    content="${content//__IMAGE_INDEX__/$image_index}"
    content="${content//__INSTALLATION_KEY__/$installation_key}"
    content="${content//__USERNAME__/$escaped_user}"
    content="${content//__PASSWORD__/$escaped_password}"
    printf '%s\n' "$content" > "$staging/Autounattend.xml"
    cp "$WINVM_REPO_DIR/guests/windows/bootstrap-openssh.ps1" \
        "$staging/bootstrap-openssh.ps1"
    cp "$WINVM_REPO_DIR/guests/windows/image-factory/bootstrap-first-logon.ps1" \
        "$staging/bootstrap-first-logon.ps1"
    cp "$WINVM_REPO_DIR/guests/windows/image-factory/startup.nsh" \
        "$staging/startup.nsh"
    cp "$public_key" "$staging/controller.pub"
    find "$staging" -type d -exec chmod 700 {} +
    find "$staging" -type f -exec chmod 600 {} +
    if command -v xmllint >/dev/null 2>&1; then
        xmllint --noout "$staging/Autounattend.xml"
    fi
    if grep -Eq '__[A-Z_]+__' "$staging/Autounattend.xml"; then
        printf 'Rendered answer file contains unresolved placeholders.\n' >&2
        return 1
    fi
    local seed_output="$FACTORY_ROOT/winvm-seed.iso"
    local boot_output="$FACTORY_ROOT/winvm-boot.img"
    if [[ -e "$seed_output" || -e "$boot_output" ]]; then
        printf 'Factory seed media already exists; remove it explicitly.\n' >&2
        return 1
    fi
    if ! command -v hdiutil >/dev/null 2>&1; then
        printf 'hdiutil is required to build answer media.\n' >&2
        return 1
    fi
    hdiutil makehybrid -quiet -iso -joliet \
        -default-volume-name WINVM_SEED -o "$seed_output" "$staging"
    local media_image
    media_build="$(mktemp -d "$FACTORY_ROOT/.seed-media.XXXXXX")"
    media_mount="$media_build/mount"
    mkdir "$media_mount"
    hdiutil create -quiet -size 2m \
        -fs 'MS-DOS FAT12' -layout NONE -type UDTO \
        -volname WINVM_BOOT "$media_build/winvm-boot"
    media_image="$media_build/winvm-boot.cdr"
    hdiutil attach -nobrowse -mountpoint "$media_mount" \
        "$media_image" >/dev/null
    media_attached=1
    cp "$staging/startup.nsh" "$media_mount/startup.nsh"
    hdiutil detach "$media_mount" >/dev/null
    media_attached=0
    mv "$media_image" "$boot_output"
    chmod 600 "$seed_output" "$boot_output"
    printf 'seed media rendered in ignored factory storage\n'
}

command="${1:-}"
if [[ -n "$command" ]]; then shift; fi
case "$command" in
    validate-media) validate_media "$@" ;;
    prepare-install-media) prepare_install_media "$@" ;;
    render-seed) render_seed "$@" ;;
    help|-h|--help) usage ;;
    *) usage >&2; exit 2 ;;
esac
