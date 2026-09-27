#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

[[ "$WINVM_PROVIDER" == libvirt-linux ]] || exit 1
[[ -n "${MACHINE_CONTROL_CLAIM_ID:-}" ]] || exit 1
"$WINVM_REPO_DIR/bin/winvm" claim-check \
    --claim-id "$MACHINE_CONTROL_CLAIM_ID" --json >/dev/null
ip="$("$(winvm_provider_path)" ip)"
exec "${WINVM_DIRECT_SSH_BIN:-ssh}" -o BatchMode=yes -o ProxyCommand=none \
    -o "HostName=$ip" -o "HostKeyAlias=$(winvm_ssh_host_key_alias)" \
    -o CheckHostIP=no -p "$WINVM_SSH_PORT" "$@"
