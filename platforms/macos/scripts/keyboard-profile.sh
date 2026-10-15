#!/usr/bin/env bash
# Configure only a claimed virtual Mac. The helper independently refuses hosts.
set -euo pipefail
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
macvm_require_host
macvm_assert_mutation_target
command="${1:-status}"
case "$command" in
    install|status|standard|alternate) ;;
    *) printf 'Usage: macvm keyboard-profile install|status|standard|alternate\n' >&2; exit 2 ;;
esac
readonly remote="/Users/$MACVM_GUEST_USER/Library/Application Support/machine-control-keyboard/environment"
if [[ "$command" == install ]]; then
    scratch="$(mktemp -d "${TMPDIR:-/tmp}/mc-keyboard-profile.XXXXXX")"
    trap 'rm -rf -- "$scratch"' EXIT
    xcrun swiftc "$MACVM_REPO_DIR/guests/macos/keyboard-fixture/environment.swift" -o "$scratch/environment"
    macvm_exec /bin/mkdir -p "$(dirname "$remote")"
    macvm_exec -i /usr/bin/tee "$remote.new" < "$scratch/environment" >/dev/null
    macvm_exec /bin/chmod 755 "$remote.new"
    macvm_exec /bin/mv -f "$remote.new" "$remote"
    macvm_exec "$remote" install-profile
elif [[ "$command" == standard ]]; then
    macvm_exec "$remote" select com.apple.keylayout.US >/dev/null
    macvm_exec "$remote" remap default
elif [[ "$command" == alternate ]]; then
    macvm_exec "$remote" profile
else
    macvm_exec "$remote" status
fi
