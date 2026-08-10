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
  image-factory.sh render-seed ARCH USERNAME IMAGE_INDEX SECRET_FILE PUBLIC_KEY GUEST_TOOLS_ISO

The rendered seed is written under ignored .factory.local. SECRET_FILE must be
mode 0600, contain one non-empty line, and is never accepted as an argument or
environment value. GUEST_TOOLS_ISO must be UTM Windows Guest Tools media. Its
drivers and installer are copied into the private seed so Windows Setup sees
one authoritative Autounattend.xml. The output contains plaintext setup
credentials and must be detached and securely discarded after bootstrap.
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

render_seed() {
    if [[ $# -ne 6 ]]; then usage >&2; return 2; fi
    local architecture="$1" username="$2" image_index="$3"
    local secret_file="$4" public_key="$5" guest_tools_iso="$6"
    case "$architecture" in arm64|amd64) ;; *) usage >&2; return 2 ;; esac
    if [[ ! "$username" =~ ^[A-Za-z][A-Za-z0-9_.-]{0,31}$ ||
        ! "$image_index" =~ ^[1-9][0-9]*$ ]]; then
        printf 'Username or image index is invalid.\n' >&2
        return 2
    fi
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
    local staging
    staging="$(mktemp -d "$FACTORY_ROOT/.seed.XXXXXX")"
    local tools_mount="$staging/guest-tools" tools_attached=0
    cleanup_seed_render() {
        if [[ "$tools_attached" == "1" ]]; then
            hdiutil detach "$tools_mount" >/dev/null 2>&1 || true
        fi
        rm -rf -- "$staging"
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
    local output="$FACTORY_ROOT/winvm-seed.iso"
    if [[ -e "$output" ]]; then
        printf 'Factory seed already exists; remove it explicitly before rendering.\n' >&2
        return 1
    fi
    if ! command -v hdiutil >/dev/null 2>&1; then
        printf 'hdiutil is required to build answer media.\n' >&2
        return 1
    fi
    hdiutil makehybrid -quiet -iso -joliet \
        -default-volume-name WINVM_SEED -o "$output" "$staging"
    chmod 600 "$output"
    printf 'seed media rendered in ignored factory storage\n'
}

command="${1:-}"
if [[ -n "$command" ]]; then shift; fi
case "$command" in
    validate-media) validate_media "$@" ;;
    render-seed) render_seed "$@" ;;
    help|-h|--help) usage ;;
    *) usage >&2; exit 2 ;;
esac
