#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
macvm_require_host
macvm_assert_mutation_target
operation="${1:-}"
case "$operation" in
    install|inspect|disable|uninstall) ;;
    *) printf 'Usage: macvm unlock-provider install --appliance | inspect | disable | uninstall\n' >&2; exit 2 ;;
esac
if [[ "$operation" == install ]]; then
    [[ $# == 2 && "$2" == --appliance ]] || { printf 'Installation requires explicit --appliance opt-in\n' >&2; exit 2; }
else
    [[ $# == 1 ]] || exit 2
fi
if [[ "$operation" == inspect ]]; then
    # Inspection must not build, stage, install, or launch anything in the guest.
    macvm_resident_request '{"operation":"status"}' | jq '.data.unlock'
    exit 0
fi
# Host build only; all privileged installation occurs inside the exact claimed target.
build="$(mktemp -d "${TMPDIR:-/tmp}/mc-unlock-build.XXXXXX")"
remote=""
cleanup() {
    [[ -z "$remote" ]] || macvm_exec /bin/rm -rf -- "$remote" >/dev/null 2>&1 || true
    /bin/rm -rf -- "$build"
}
trap cleanup EXIT

"$MACVM_REPO_DIR/guests/macos/unlock/build.sh" "$build"
remote="$(macvm_exec /usr/bin/mktemp -d /tmp/mc-unlock-install.XXXXXX)"
[[ "$remote" =~ ^/tmp/mc-unlock-install\.[A-Za-z0-9]+$ ]] || exit 1
/usr/bin/tar -C "$build" -cf - . | macvm_exec -i /usr/bin/tar -C "$remote" -xf -
args=("$operation")
if [[ "$operation" == install ]]; then
    uid="$(macvm_exec /usr/bin/id -u)"
    [[ "$uid" =~ ^[0-9]+$ ]] && [[ "$uid" != 0 ]] || exit 1
    args+=(--appliance-uid "$uid" "$(macvm_remote_ui_binary)")
fi
macvm_exec /usr/bin/sudo -n "$remote/mc-unlock-install" "${args[@]}"
