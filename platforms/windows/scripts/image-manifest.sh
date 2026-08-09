#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: image-manifest.sh ABSOLUTE_BUNDLE.utm [--oobe-confirmed]

Write or atomically refresh the adjacent private image manifest. The optional
flag records that a disposable boot visibly reached Windows OOBE.
EOF
}

if [[ $# -lt 1 || $# -gt 2 || "$1" != /* || "${1##*.}" != "utm" ||
    ! -d "$1" ]]; then
    usage >&2
    exit 2
fi
bundle="$1"
oobe_confirmed=false
if [[ $# -eq 2 ]]; then
    [[ "$2" == "--oobe-confirmed" ]] || { usage >&2; exit 2; }
    oobe_confirmed=true
fi
for command_name in jq plutil shasum; do
    command -v "$command_name" >/dev/null 2>&1 || {
        printf 'Required command not found: %s\n' "$command_name" >&2
        exit 1
    }
done
config="$bundle/config.plist"
if [[ ! -f "$config" ]]; then
    printf 'UTM bundle has no config.plist.\n' >&2
    exit 1
fi

manifest="${bundle%.utm}.manifest.json"
temporary="$(mktemp "$manifest.XXXXXX")"
trap 'rm -f -- "$temporary"' EXIT
bundle_kib="$(du -sk "$bundle" | awk '{print $1}')"
config_sha256="$(shasum -a 256 "$config" | awk '{print $1}')"
architecture="$(plutil -extract System.Architecture raw -o - "$config")"
backend="$(plutil -extract Backend raw -o - "$config")"
disk_count="$(plutil -extract Drive json -o - "$config" | \
    jq '[.[] | select(.ImageType == "Disk")] | length')"

jq -n \
    --arg created_at_utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg bundle_name "$(basename "$bundle")" \
    --arg architecture "$architecture" \
    --arg backend "$backend" \
    --arg config_sha256 "$config_sha256" \
    --argjson bundle_bytes "$((bundle_kib * 1024))" \
    --argjson disk_count "$disk_count" \
    --argjson oobe_confirmed "$oobe_confirmed" \
    '{schema: "winvm-image-manifest/v0", created_at_utc: $created_at_utc, bundle_name: $bundle_name, provider: "utm-macos", backend: $backend, architecture: $architecture, bundle_bytes: $bundle_bytes, disk_count: $disk_count, config_sha256: $config_sha256, generalization: {profile: "same-controller-utm-appliance", expected_next_boot: "oobe"}, verification: {disposable_oobe_confirmed: $oobe_confirmed, persistent_first_boot_performed: false}}' \
    > "$temporary"
chmod 600 "$temporary"
mv "$temporary" "$manifest"
trap - EXIT
printf 'private image manifest written\n'
