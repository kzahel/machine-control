#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly GUEST_SCRIPT="$WINVM_REPO_DIR/guests/windows/image-factory/prepare-generalized-image.ps1"
readonly REMOTE_SCRIPT='C:/Users/Public/winvm-prepare-generalized-image.ps1'

usage() {
    cat <<'EOF'
Usage: winvm generalize --check|--confirm-target

Preflight or generalize the UUID-pinned candidate with Sysprep /generalize
/oobe /shutdown /mode:vm. The confirmation path strips auto-logon and SSH host
identity, retains the authorized controller public key, and waits for a clean
provider-observed shutdown.
EOF
}

case "${1:-}" in
    --check) mode=check ;;
    --confirm-target) mode=execute ;;
    *) usage >&2; exit 2 ;;
esac

"$WINVM_REPO_DIR/bin/winvm" assert-target generalize >/dev/null
for command_name in ssh scp; do winvm_require_command "$command_name"; done
scp -q "$GUEST_SCRIPT" "$WINVM_SSH_HOST:$REMOTE_SCRIPT"

if [[ "$mode" == "check" ]]; then
    exec ssh -o BatchMode=yes "$WINVM_SSH_HOST" \
        "powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $REMOTE_SCRIPT -CheckOnly"
fi

set +e
ssh -o BatchMode=yes "$WINVM_SSH_HOST" \
    "powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $REMOTE_SCRIPT -ConfirmGeneralize" \
    >/dev/null 2>&1
set -e

deadline=$((SECONDS + 900))
while (( SECONDS < deadline )); do
    state="$("$WINVM_REPO_DIR/bin/winvm" status 2>/dev/null || true)"
    if [[ "$state" == "stopped" ]]; then
        printf 'generalized shutdown observed\n'
        exit 0
    fi
    sleep 2
done
printf 'Timed out waiting for generalized target shutdown.\n' >&2
exit 1
