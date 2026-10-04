#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

# Historical executable name; the carrier is provider-independent.
[[ "$WINVM_PROVIDER" == libvirt-linux || "$WINVM_PROVIDER" == utm-macos ]] || exit 1
if [[ "${MACHINE_CONTROL_CLAIM_POLICY:-required}" != optional ||
      -n "${MACHINE_CONTROL_CLAIM_ID:-}" ]]; then
    [[ -n "${MACHINE_CONTROL_CLAIM_ID:-}" ]] || exit 1
    "$WINVM_REPO_DIR/bin/winvm" claim-check \
        --claim-id "$MACHINE_CONTROL_CLAIM_ID" --json >/dev/null
fi
ip="$("$(winvm_provider_path)" ip)"
[[ -n "$ip" && "$ip" != *[[:space:]]* ]] || {
    printf 'The claimed target has no usable SSH address.\n' >&2
    exit 1
}
exec "${WINVM_DIRECT_SCP_BIN:-scp}" -o BatchMode=yes -o ProxyCommand=none \
    -o "HostName=$ip" -o "HostKeyAlias=$(winvm_ssh_host_key_alias)" \
    -o CheckHostIP=no -P "$WINVM_SSH_PORT" "$@"
