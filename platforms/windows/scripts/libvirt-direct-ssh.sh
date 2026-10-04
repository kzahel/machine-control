#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

# Retain the historical executable name for deployed integrations. Both owned
# providers resolve the exact claimed target instead of a controller proxy.
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
exec "${WINVM_DIRECT_SSH_BIN:-ssh}" -o BatchMode=yes -o ProxyCommand=none \
    -o "HostName=$ip" -o "HostKeyAlias=$(winvm_ssh_host_key_alias)" \
    -o CheckHostIP=no -p "$WINVM_SSH_PORT" "$@"
