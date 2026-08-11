#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

if [[ $# -ne 1 ]]; then
    printf 'Usage: winvm control JSON\n' >&2
    exit 2
fi
request="$1"
if ! jq -e 'type == "object" and (.operation | type == "string") and
        (.operation | length > 0)' <<<"$request" >/dev/null 2>&1; then
    printf 'Control request must be a JSON object with operation\n' >&2
    exit 2
fi
request_base64="$(printf '%s' "$request" | base64 | tr -d '\n')"

read -r -d '' powershell_script <<POWERSHELL || true
\$ErrorActionPreference = 'Stop'
\$ProgressPreference = 'SilentlyContinue'
\$executable = Join-Path \$env:ProgramData 'MachineControl\runtime\machine-control-windows.exe'
if (-not (Test-Path -LiteralPath \$executable -PathType Leaf)) {
    throw 'MachineControl resident client is not installed'
}
\$json = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String('$request_base64'))
\$json | & \$executable call
if (\$LASTEXITCODE -ne 0) { exit \$LASTEXITCODE }
POWERSHELL

winvm_powershell "$powershell_script"
