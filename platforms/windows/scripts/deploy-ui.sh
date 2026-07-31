#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

skip_winapp=0
case "${1:-}" in
    '') ;;
    --skip-winapp-install) skip_winapp=1 ;;
    --help|-h)
        cat <<'EOF'
Usage: winvm deploy-ui [--skip-winapp-install]

Installs Microsoft WinApp CLI when necessary, deploys the Windows session
relay, registers its interactive-logon scheduled task, and verifies health.
EOF
        exit 0
        ;;
    *)
        printf 'Unknown option: %s\n' "$1" >&2
        exit 2
        ;;
esac

for tool in ssh scp iconv base64 jq; do
    winvm_require_command "$tool"
done

if [[ "$WINVM_GUEST_DRIVER" != "windows" ]]; then
    printf 'UI deployment is not implemented for guest driver: %s\n' \
        "$WINVM_GUEST_DRIVER" >&2
    exit 1
fi

if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$WINVM_SSH_HOST" exit; then
    printf 'Key-only SSH is unavailable. Run stage-bootstrap and configure SSH first.\n' >&2
    exit 1
fi

if (( ! skip_winapp )); then
    read -r -d '' install_winapp <<'POWERSHELL' || true
$ErrorActionPreference = 'Stop'
if (-not (Get-Command winapp.exe -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw 'winget.exe is required to install Microsoft WinApp CLI'
    }
    & winget.exe install --id Microsoft.WinAppCli --exact `
        --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed with exit code $LASTEXITCODE"
    }
}
(Get-Command winapp.exe -ErrorAction Stop).Source
POWERSHELL
    winvm_powershell "$install_winapp"
fi

read -r -d '' create_directory <<'POWERSHELL' || true
$directory = Join-Path $env:LOCALAPPDATA 'winvm-testbed'
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$directory
POWERSHELL
winvm_powershell "$create_directory" >/dev/null

scp \
    "$WINVM_REPO_DIR/guests/windows/ui/ui-relay.ps1" \
    "$WINVM_REPO_DIR/guests/windows/ui/ui-client.ps1" \
    "$WINVM_REPO_DIR/guests/windows/ui/install-ui-relay.ps1" \
    "$WINVM_REPO_DIR/guests/windows/ui/uninstall-ui-relay.ps1" \
    "$WINVM_SSH_HOST:$WINVM_UI_REMOTE_RELATIVE/"

if [[ "$WINVM_UI_PIPE_NAME" == *"'"* || "$WINVM_UI_TASK_NAME" == *"'"* ]]; then
    printf 'UI pipe and task names cannot contain single quotes\n' >&2
    exit 1
fi

read -r -d '' install_relay <<'POWERSHELL' || true
$installer = Join-Path $env:LOCALAPPDATA 'winvm-testbed\install-ui-relay.ps1'
& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
    -File $installer `
    -PipeName '__WINVM_UI_PIPE_NAME__' `
    -TaskName '__WINVM_UI_TASK_NAME__'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
POWERSHELL
install_relay="${install_relay//__WINVM_UI_PIPE_NAME__/$WINVM_UI_PIPE_NAME}"
install_relay="${install_relay//__WINVM_UI_TASK_NAME__/$WINVM_UI_TASK_NAME}"
winvm_powershell "$install_relay"

"$WINVM_REPO_DIR/bin/winui" health
