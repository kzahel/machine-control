#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

if [[ $# -lt 1 || $# -gt 2 || ! "$1" =~ ^[0-9a-fA-F]{32}$ ]]; then
    printf 'Usage: winvm artifact ARTIFACT_ID [OUTPUT.png]\n' >&2
    exit 2
fi
artifact_id="${1,,}"
if [[ $# -eq 2 ]]; then
    output="$2"
    if [[ -e "$output" || ! -d "$(dirname "$output")" ]]; then
        printf 'Artifact output must be absent with an existing parent\n' >&2
        exit 2
    fi
else
    output_directory="$(mktemp -d "${TMPDIR:-/tmp}/winvm-artifact.XXXXXX")"
    output="$output_directory/$artifact_id.png"
fi

read -r -d '' powershell_script <<POWERSHELL || true
\$ErrorActionPreference = 'Stop'
\$ProgressPreference = 'SilentlyContinue'
\$root = Join-Path \$env:ProgramData 'MachineControl\artifacts'
\$path = Join-Path \$root '$artifact_id.png'
if (-not (Test-Path -LiteralPath \$path -PathType Leaf)) {
    throw 'Resident artifact is unavailable'
}
[Convert]::ToBase64String([IO.File]::ReadAllBytes(\$path))
POWERSHELL

encoded="$(winvm_powershell "$powershell_script" | tr -d '\r\n')"
if [[ "$(uname -s)" == Darwin ]]; then
    printf '%s' "$encoded" | base64 -D >"$output"
else
    printf '%s' "$encoded" | base64 --decode >"$output"
fi
if [[ ! -s "$output" || "$(od -An -tx1 -N8 "$output" | tr -d ' \n')" != \
        89504e470d0a1a0a ]]; then
    printf 'Resident artifact is not a PNG\n' >&2
    exit 1
fi
printf '%s\n' "$output"
