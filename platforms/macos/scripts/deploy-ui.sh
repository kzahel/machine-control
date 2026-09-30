#!/usr/bin/env bash
# Deploy the shared Machine Control.app into the guest: the same bundle,
# per-user LaunchAgent, and socket used on a physical host, with the
# appliance deployment policy. A guest still running the pre-shared
# testbed resident is migrated once the new identity holds its consent.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

macvm_require_host
macvm_assert_mutation_target

force=0
case "${1:-}" in
    '') ;;
    --force) force=1 ;;
    -h|--help)
        printf 'Usage: macvm deploy-ui [--force]\n'
        exit 0
        ;;
    *)
        printf 'Unknown deploy-ui option: %s\n' "$1" >&2
        exit 2
        ;;
esac

readonly package_dir="$MACVM_REPO_DIR/resident"
readonly remote_directory="$(macvm_remote_ui_dir)"
readonly remote_app="$(macvm_remote_ui_app)"
readonly remote_control_cli="$(macvm_remote_control_cli)"
readonly remote_staging="$remote_directory/staging"
readonly remote_installer="$remote_directory/install-user.sh"
readonly legacy_app="$(macvm_remote_legacy_ui_app)"
readonly legacy_label="$(macvm_remote_legacy_resident_label)"
readonly control_cli_file="$MACVM_REPO_DIR/guests/macos/ui/machine-control"

if ! macvm_exec /usr/bin/true; then
    printf 'Guest command transport is unavailable; read docs/bootstrap.md\n' >&2
    exit 1
fi

# The resident reads its deployment policy from a root-owned file and treats
# anything absent or untrusted as a personal workstation. Tart guests are
# disposable appliances, so install the standing policy before the resident.
policy_file="$package_dir/policies/appliance.json"
remote_policy_dir='/Library/Application Support/MachineControl'
remote_policy="$remote_policy_dir/policy.json"
local_policy_hash="$(/usr/bin/shasum -a 256 "$policy_file" | /usr/bin/awk '{print $1}')"
remote_policy_hash="$(macvm_exec /usr/bin/shasum -a 256 "$remote_policy" 2>/dev/null |
    /usr/bin/awk '{print $1}' || true)"
policy_owner="$(macvm_exec /usr/bin/stat -f '%Su:%Sg:%Lp' "$remote_policy" 2>/dev/null || true)"
policy_changed=false
if [[ "$local_policy_hash" != "$remote_policy_hash" || "$policy_owner" != 'root:wheel:644' ]]; then
    macvm_exec /usr/bin/sudo -n /usr/bin/install -d -o root -g wheel -m 755 \
        "$remote_policy_dir"
    macvm_exec -i /usr/bin/sudo -n /usr/bin/tee "$remote_policy.new" \
        < "$policy_file" >/dev/null
    macvm_exec /usr/bin/sudo -n /usr/sbin/chown root:wheel "$remote_policy.new"
    macvm_exec /usr/bin/sudo -n /bin/chmod 644 "$remote_policy.new"
    macvm_exec /usr/bin/sudo -n /bin/mv -f "$remote_policy.new" "$remote_policy"
    printf 'Installed appliance deployment policy at %s\n' "$remote_policy"
    policy_changed=true
fi

source_digest="$(
    cd "$MACVM_REPO_DIR"
    for file in resident/Sources/macui/*.swift resident/app/* \
            resident/policies/*.json resident/scripts/build-app.sh \
            resident/scripts/install-user.sh guests/macos/unlock/Probe.m \
            guests/macos/unlock/Session.h guests/macos/ui/machine-control; do
        printf '%s\n' "$file"
        /bin/cat "$file"
    done | /usr/bin/shasum -a 256 | /usr/bin/awk '{print $1}'
)"
remote_digest="$(macvm_exec /bin/cat "$remote_directory/bundle-digest" 2>/dev/null || true)"
bundle_current=false
if (( ! force )) && [[ "$source_digest" == "$remote_digest" ]] &&
        macvm_exec /usr/bin/codesign --verify --strict "$remote_app" >/dev/null 2>&1 &&
        macvm_exec /bin/test -f "$(macvm_remote_resident_plist)" >/dev/null 2>&1; then
    bundle_current=true
fi

if [[ "$bundle_current" == true ]]; then
    printf 'Machine Control is already current at %s\n' "$remote_app"
    if [[ "$policy_changed" == true ]]; then
        "$MACVM_REPO_DIR/bin/macui" resident-stop >/dev/null 2>&1 || true
    fi
    "$MACVM_REPO_DIR/bin/macui" resident-start >/dev/null
else
    guest_arch="$(macvm_exec /usr/bin/uname -m)"
    build_dir="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/macvm-app.XXXXXX")"
    trap '/bin/rm -rf -- "$build_dir"' EXIT
    "$package_dir/scripts/build-app.sh" --output "$build_dir" --arch "$guest_arch" >/dev/null
    macvm_exec /bin/rm -rf "$remote_staging"
    macvm_exec /bin/mkdir -p "$remote_staging" "$(/usr/bin/dirname "$remote_control_cli")"
    /usr/bin/tar -C "$build_dir" -cf - 'Machine Control.app' |
        macvm_exec -i /usr/bin/tar -xf - -C "$remote_staging"
    macvm_exec -i /usr/bin/tee "$remote_installer" \
        < "$package_dir/scripts/install-user.sh" >/dev/null
    macvm_exec /bin/bash "$remote_installer" --app "$remote_staging/Machine Control.app"
    macvm_exec /bin/rm -rf "$remote_staging"
    macvm_exec -i /usr/bin/tee "$remote_control_cli" < "$control_cli_file" >/dev/null
    macvm_exec /bin/chmod 755 "$remote_control_cli"
    printf '%s\n' "$source_digest" |
        macvm_exec -i /usr/bin/tee "$remote_directory/bundle-digest" >/dev/null
    printf 'Deployed %s\n' "$remote_app"
fi

consent_ready() {
    local status
    status="$(macvm_resident_request '{"operation":"status"}' 2>/dev/null || true)"
    [[ "$(/usr/bin/jq -r '.data.semanticAuthorizationState // empty' <<<"$status")" == ready &&
       "$(/usr/bin/jq -r '.data.captureAuthorizationState // empty' <<<"$status")" == ready ]]
}

if macvm_exec /bin/test -d "$legacy_app" >/dev/null 2>&1; then
    if ! consent_ready; then
        printf 'Granting the shared application consent through the testbed resident\n'
        if "$SCRIPT_DIR/grant-resident-consent.sh"; then
            # A new Screen Recording grant is visible only to a new process.
            "$MACVM_REPO_DIR/bin/macui" resident-restart >/dev/null
        fi
    fi
    if consent_ready; then
        macvm_exec /bin/launchctl bootout \
            "gui/$(macvm_exec /usr/bin/id -u)/$legacy_label" >/dev/null 2>&1 || true
        macvm_exec /bin/rm -f "/Users/$MACVM_GUEST_USER/Library/LaunchAgents/$legacy_label.plist" \
            "$(macvm_remote_legacy_control_socket)"
        macvm_exec /bin/rm -rf "$legacy_app" "$remote_directory/src" \
            "$remote_directory/macui.swift" "$remote_directory/source-digest" \
            "$remote_directory/Probe.m" "$remote_directory/Session.h" \
            "$remote_directory/resident.log"
        printf 'Retired the testbed resident %s\n' "$legacy_app"
    else
        printf 'The testbed resident remains until Machine Control has Accessibility and Screen Recording\n' >&2
    fi
fi

macvm_resident_request '{"operation":"status"}'
