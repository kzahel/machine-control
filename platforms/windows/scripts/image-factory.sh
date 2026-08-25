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
verified prompted loader in a private copy with Microsoft's no-prompt loader
from that same ISO. SECRET_FILE must be mode 0600, contain one
non-empty line, and is never accepted as an argument or environment value.
EDITION is currently windows-11-pro and selects Microsoft's public
installation-only KMS client setup key; it does not activate Windows.
GUEST_TOOLS_ISO must be UTM Windows Guest Tools media or Fedora's stable
virtio-win media. Its drivers and installer are copied into the private seed
so Windows Setup sees one authoritative Autounattend.xml. The output contains
plaintext setup credentials and must be detached and securely discarded after
bootstrap. Linux renders the data seed used by libvirt; macOS additionally
renders UTM's firmware-shell boot image.
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
    if [[ "$(uname -s)" == Darwin ]]; then
        size="$(stat -f %z "$1")"
    else
        size="$(stat -c %s "$1")"
    fi
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
    for command_name in perl cp; do
        if ! command -v "$command_name" >/dev/null 2>&1; then
            printf 'Required command not found: %s\n' "$command_name" >&2
            return 1
        fi
    done
    mkdir -p "$FACTORY_ROOT"
    chmod 700 "$FACTORY_ROOT"
    if ! command -v hdiutil >/dev/null 2>&1 &&
            ! command -v 7z >/dev/null 2>&1; then
        printf 'hdiutil or 7z is required to inspect installation media.\n' >&2
        return 1
    fi
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
    if [[ "$(uname -s)" == Darwin ]]; then
        if ! cp -c "$source_iso" "$output" 2>/dev/null; then
            cp "$source_iso" "$output"
        fi
    else
        cp --reflink=auto --sparse=always "$source_iso" "$output"
    fi
    if command -v hdiutil >/dev/null 2>&1; then
        source_device="$(hdiutil attach -readonly -nobrowse \
            -mountpoint "$mount" "$source_iso" | \
            awk 'NF { device=$1 } END { print device }')"
        if [[ -z "$source_device" ]]; then
            printf 'Windows media did not expose an attached device.\n' >&2
            return 1
        fi
    else
        7z x -y -o"$mount" "$source_iso" \
            efi/microsoft/boot/cdboot.efi \
            efi/microsoft/boot/cdboot_noprompt.efi >/dev/null
    fi
    local prompted="$mount/efi/microsoft/boot/cdboot.efi"
    local no_prompt="$mount/efi/microsoft/boot/cdboot_noprompt.efi"
    if [[ ! -f "$prompted" || ! -f "$no_prompt" ]]; then
        printf 'Windows media lacks the expected CD boot loaders.\n' >&2
        return 1
    fi
    local boot_image="$build/efi-boot.img"
    local patch_state="$build/patch-state"
    perl - "$source_iso" "$output" "$prompted" "$no_prompt" \
        "$boot_image" "$patch_state" <<'PERL'
use strict;
use warnings;

my ($source, $output, $prompted_path, $no_prompt_path, $boot_path,
    $state_path) = @ARGV;
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
my $default_platform = ord(substr($catalog, 1, 1));
my $default_entry = substr($catalog, 32, 32);
if ($default_platform == 0xef && ord(substr($default_entry, 0, 1)) == 0x88) {
    $entry = $default_entry;
}
for (my $offset = 64; !defined($entry) && $offset + 32 <= length($catalog);) {
    my $header = substr($catalog, $offset, 32);
    my $indicator = ord(substr($header, 0, 1));
    last if $indicator == 0;
    if ($indicator != 0x90 && $indicator != 0x91) {
        $offset += 32;
        next;
    }
    my $platform = ord(substr($header, 1, 1));
    my $count = unpack('v', substr($header, 2, 2));
    for my $index (1 .. $count) {
        my $entry_offset = $offset + $index * 32;
        $entry_offset + 32 <= length($catalog)
            or die "truncated El Torito section\n";
        my $candidate = substr($catalog, $entry_offset, 32);
        if ($platform == 0xef && ord(substr($candidate, 0, 1)) == 0x88) {
            $entry = $candidate;
            last;
        }
    }
    $offset += ($count + 1) * 32;
}
defined $entry or die "bootable EFI El Torito entry not found\n";
my $image_lba = unpack('V', substr($entry, 8, 4));
$image_lba > 0 or die "invalid boot image extent\n";
seek $source_fh, $image_lba * 2048, 0 or die "seek boot image: $!\n";
read($source_fh, my $boot_sector, 512) == 512 or die "read boot sector\n";
my $bytes_per_sector = unpack('v', substr($boot_sector, 11, 2));
my $total16 = unpack('v', substr($boot_sector, 19, 2));
my $total32 = unpack('V', substr($boot_sector, 32, 4));
my $total_sectors = $total16 || $total32;
my $boot_size = $bytes_per_sector * $total_sectors;
$bytes_per_sector == 512 && $boot_size >= 65536 && $boot_size <= 67108864
    or die "invalid EFI FAT boot image\n";
seek $source_fh, $image_lba * 2048, 0 or die "seek full boot image: $!\n";
read($source_fh, my $boot_image, $boot_size) == $boot_size
    or die "read full boot image\n";

sub read_file {
    my ($path) = @_;
    open my $fh, '<:raw', $path or die "open loader: $!\n";
    local $/;
    return <$fh>;
}
my $prompted = read_file($prompted_path);
my $no_prompt = read_file($no_prompt_path);
length($prompted) > 0 && length($no_prompt) > 0
    or die "Windows boot loaders are empty\n";
my $loader_offset = index($boot_image, $prompted);
$loader_offset >= 0 or die "prompted loader not found in boot image\n";
index($boot_image, $prompted, $loader_offset + 1) < 0
    or die "prompted loader is not unique in boot image\n";

if (length($prompted) == length($no_prompt)) {
    open my $output_fh, '+<:raw', $output or die "open output ISO: $!\n";
    my $patch_offset = $image_lba * 2048 + $loader_offset;
    seek $output_fh, $patch_offset, 0 or die "seek output loader: $!\n";
    print {$output_fh} $no_prompt or die "write no-prompt loader: $!\n";
    seek $output_fh, $patch_offset, 0 or die "verify output loader seek: $!\n";
    read($output_fh, my $verified, length($no_prompt)) == length($no_prompt)
        or die "verify output loader read\n";
    $verified eq $no_prompt or die "output loader verification failed\n";
    open my $state_fh, '>', $state_path or die "open patch state: $!\n";
    print {$state_fh} "direct\n";
} else {
    open my $boot_fh, '>:raw', $boot_path or die "open boot image: $!\n";
    print {$boot_fh} $boot_image or die "write boot image: $!\n";
    close $boot_fh or die "close boot image: $!\n";
    open my $state_fh, '>', $state_path or die "open patch state: $!\n";
    print {$state_fh} "fat $image_lba $boot_size\n";
}
PERL
    local patch_mode image_lba image_size
    read -r patch_mode image_lba image_size <"$patch_state"
    if [[ "$patch_mode" == fat ]]; then
        for command_name in mcopy mdir; do
            if ! command -v "$command_name" >/dev/null 2>&1; then
                printf 'Required command not found: %s\n' "$command_name" >&2
                return 1
            fi
        done
        local loader_name=""
        if mdir -i "$boot_image" ::/EFI/BOOT/BOOTX64.EFI >/dev/null 2>&1; then
            loader_name=BOOTX64.EFI
        elif mdir -i "$boot_image" ::/EFI/BOOT/BOOTAA64.EFI >/dev/null 2>&1; then
            loader_name=BOOTAA64.EFI
        else
            printf 'EFI boot image lacks the expected architecture loader.\n' >&2
            return 1
        fi
        mcopy -o -i "$boot_image" "$no_prompt" "::/EFI/BOOT/$loader_name"
        local verified_loader="$build/verified-loader.efi"
        mcopy -i "$boot_image" "::/EFI/BOOT/$loader_name" "$verified_loader"
        cmp -s "$no_prompt" "$verified_loader" || {
            printf 'EFI no-prompt loader replacement could not be verified.\n' >&2
            return 1
        }
        perl - "$output" "$boot_image" "$image_lba" "$image_size" <<'PERL'
use strict;
use warnings;
my ($output, $boot_path, $image_lba, $image_size) = @ARGV;
open my $boot_fh, '<:raw', $boot_path or die "open boot image: $!\n";
read($boot_fh, my $boot_image, $image_size) == $image_size
    or die "read boot image: $!\n";
open my $output_fh, '+<:raw', $output or die "open output ISO: $!\n";
seek $output_fh, $image_lba * 2048, 0 or die "seek output boot image: $!\n";
print {$output_fh} $boot_image or die "write output boot image: $!\n";
seek $output_fh, $image_lba * 2048, 0 or die "verify boot image seek: $!\n";
read($output_fh, my $verified, $image_size) == $image_size
    or die "verify boot image read\n";
$verified eq $boot_image or die "output boot image verification failed\n";
PERL
    elif [[ "$patch_mode" != direct ]]; then
        printf 'Windows media preparation returned invalid patch state.\n' >&2
        return 1
    fi
    if [[ -n "$source_device" ]]; then
        hdiutil detach "$source_device" >/dev/null
        source_device=""
    fi
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
    if [[ "$(uname -s)" == Darwin ]]; then
        mode="$(stat -f %Lp "$secret_file")"
    else
        mode="$(stat -c %a "$secret_file")"
    fi
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
    local driver_architecture hardware_compatibility=""
    if [[ "$architecture" == "arm64" ]]; then
        driver_architecture="ARM64"
        hardware_compatibility='<RunSynchronous>
        <RunSynchronousCommand wcm:action="add"><Order>1</Order><Path>reg add HKLM\System\Setup\LabConfig /v BypassCPUCheck /t REG_DWORD /d 1 /f</Path></RunSynchronousCommand>
        <RunSynchronousCommand wcm:action="add"><Order>2</Order><Path>reg add HKLM\System\Setup\LabConfig /v BypassRAMCheck /t REG_DWORD /d 1 /f</Path></RunSynchronousCommand>
        <RunSynchronousCommand wcm:action="add"><Order>3</Order><Path>reg add HKLM\System\Setup\LabConfig /v BypassSecureBootCheck /t REG_DWORD /d 1 /f</Path></RunSynchronousCommand>
        <RunSynchronousCommand wcm:action="add"><Order>4</Order><Path>reg add HKLM\System\Setup\LabConfig /v BypassTPMCheck /t REG_DWORD /d 1 /f</Path></RunSynchronousCommand>
      </RunSynchronous>'
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
    if command -v hdiutil >/dev/null 2>&1; then
        hdiutil attach -readonly -nobrowse -mountpoint "$tools_mount" \
            "$guest_tools_iso" >/dev/null
        tools_attached=1
    elif command -v xorriso >/dev/null 2>&1; then
        xorriso -osirrox on -indev "$guest_tools_iso" -extract / \
            "$tools_mount" >/dev/null 2>&1
    else
        printf 'hdiutil or xorriso is required to inspect guest-tools media.\n' >&2
        return 1
    fi
    local installers=("$tools_mount"/utm-guest-tools-*.exe)
    if [[ -f "$tools_mount/virtio-win-guest-tools.exe" ]]; then
        installers=("$tools_mount/virtio-win-guest-tools.exe")
    fi
    if [[ ${#installers[@]} -ne 1 || ! -f "${installers[0]}" ]]; then
        printf 'Guest-tools media lacks one supported tools installer.\n' >&2
        return 1
    fi
    if [[ -d "$tools_mount/Drivers" ]]; then
        cp -R "$tools_mount/Drivers" "$staging/Drivers"
    else
        mkdir "$staging/Drivers"
        local driver_directory
        for driver_directory in Balloon NetKVM vioscsi vioserial viostor; do
            if [[ ! -d "$tools_mount/$driver_directory" ]]; then
                printf 'VirtIO media lacks a required Windows driver.\n' >&2
                return 1
            fi
            cp -R "$tools_mount/$driver_directory" "$staging/Drivers/"
        done
    fi
    chmod -R u+w "$staging/Drivers"
    cp "${installers[0]}" "$staging/"
    if [[ "$tools_attached" == "1" ]]; then
        hdiutil detach "$tools_mount" >/dev/null
        tools_attached=0
        rmdir "$tools_mount"
    fi
    local content
    content="$(<"$TEMPLATE")"
    content="${content//__ARCHITECTURE__/$architecture}"
    content="${content//__DRIVER_ARCHITECTURE__/$driver_architecture}"
    content="${content//__LANGUAGE__/$language}"
    content="${content//__IMAGE_INDEX__/$image_index}"
    content="${content//__INSTALLATION_KEY__/$installation_key}"
    content="${content//__HARDWARE_COMPATIBILITY__/$hardware_compatibility}"
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
    if [[ -e "$seed_output" ||
          "$(uname -s)" == Darwin && -e "$boot_output" ]]; then
        printf 'Factory seed media already exists; remove it explicitly.\n' >&2
        return 1
    fi
    if command -v hdiutil >/dev/null 2>&1; then
        hdiutil makehybrid -quiet -iso -joliet \
            -default-volume-name WINVM_SEED -o "$seed_output" "$staging"
    elif command -v xorriso >/dev/null 2>&1; then
        xorriso -as mkisofs -iso-level 3 -J -R -V WINVM_SEED \
            -o "$seed_output" "$staging" >/dev/null 2>&1
    else
        printf 'hdiutil or xorriso is required to build answer media.\n' >&2
        return 1
    fi
    chmod 600 "$seed_output"
    if command -v hdiutil >/dev/null 2>&1; then
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
        chmod 600 "$boot_output"
    fi
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
