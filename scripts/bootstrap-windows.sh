#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: bootstrap-windows.sh (--testbed PATH | --allow-unattested-target)
                            [--check-target]
                            [--profile development|runtime]
                            SSH_TARGET [win-arm64|win-x64]

Build, verify, transfer, install, and probe MachineControl on a testbed-ready
Windows target. When the runtime identifier is omitted, target architecture is
detected through PowerShell over the authenticated SSH carrier.

--testbed requires a provider-native identity assertion authorizing product
installation on a candidate and binds it to SSH_TARGET. The conspicuous
--allow-unattested-target escape hatch is for explicitly selected physical or
non-integrated targets. --check-target validates the assertion without making
or connecting to the target. The default development profile installs and
verifies Python 3 and the .NET 8 SDK before installing the resident runtime;
runtime installs only the resident package.
EOF
}

testbed_root=""
allow_unattested=0
check_target_only=0
profile=development
while [[ $# -gt 0 ]]; do
    case "$1" in
        --testbed)
            if [[ $# -lt 2 || -z "$2" ]]; then usage >&2; exit 2; fi
            testbed_root="$2"
            shift 2
            ;;
        --allow-unattested-target)
            allow_unattested=1
            shift
            ;;
        --check-target)
            check_target_only=1
            shift
            ;;
        --profile)
            if [[ $# -lt 2 ||
                ( "$2" != development && "$2" != runtime ) ]]; then
                usage >&2
                exit 2
            fi
            profile="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        --*)
            printf 'Unknown option: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
        *) break ;;
    esac
done

if [[ $# -lt 1 || $# -gt 2 ||
    ( -n "$testbed_root" && "$allow_unattested" -eq 1 ) ||
    ( -z "$testbed_root" && "$allow_unattested" -eq 0 ) ||
    ( "$check_target_only" -eq 1 && -z "$testbed_root" ) ]]; then
    usage >&2
    exit 2
fi

readonly ssh_target="$1"
requested_rid="${2:-}"
case "$requested_rid" in
    ""|win-arm64|win-x64) ;;
    *) usage >&2; exit 2 ;;
esac

readonly repo_root="$(cd "$(dirname "$0")/.." && pwd)"
readonly ssh_bin="${MACHINE_CONTROL_SSH_BIN:-ssh}"
readonly scp_bin="${MACHINE_CONTROL_SCP_BIN:-scp}"

if [[ -n "$testbed_root" ]]; then
    readonly assertion_command="$testbed_root/bin/winvm"
    if [[ ! -x "$assertion_command" ]]; then
        printf 'Testbed assertion command is unavailable.\n' >&2
        exit 1
    fi
    if ! command -v jq >/dev/null 2>&1; then
        printf 'Required command not found: jq\n' >&2
        exit 1
    fi
    if ! target_assertion="$($assertion_command \
            assert-target product-install --json)"; then
        printf 'Testbed target assertion refused product installation.\n' >&2
        exit 1
    fi
    if ! jq -e \
        --arg target "$ssh_target" \
        '.authorized == true and
         .identity_pin == "verified" and
         .role == "candidate" and
         .operation == "product-install" and
         .transport.ssh_alias == $target' \
        >/dev/null <<< "$target_assertion"; then
        printf 'Testbed assertion does not bind this candidate SSH target.\n' >&2
        exit 1
    fi
    if [[ "$check_target_only" -eq 1 ]]; then
        printf 'target assertion passed\n'
        exit 0
    fi
fi

for command_name in "$ssh_bin" "$scp_bin" iconv base64 jq shasum; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$command_name" >&2
        exit 1
    fi
done
if ! command -v ditto >/dev/null 2>&1 &&
    ! command -v zip >/dev/null 2>&1; then
    printf 'Either ditto or zip is required to package the runtime.\n' >&2
    exit 1
fi

encode_powershell() {
    iconv -f UTF-8 -t UTF-16LE | base64 | tr -d '\n'
}

remote_powershell() {
    local script="$1" encoded error_log exit_code
    encoded="$(printf '%s' "$script" | encode_powershell)"
    error_log="$(mktemp "${TMPDIR:-/tmp}/machine-control-powershell.XXXXXX")"
    if "$ssh_bin" -o BatchMode=yes "$ssh_target" \
        "powershell.exe -NoLogo -NoProfile -NonInteractive -OutputFormat Text -EncodedCommand $encoded" \
        2>"$error_log"; then
        rm -f -- "$error_log"
        return 0
    else
        exit_code=$?
        cat "$error_log" >&2
        rm -f -- "$error_log"
        return "$exit_code"
    fi
}

if [[ -z "$requested_rid" ]]; then
    read -r -d '' architecture_script <<'POWERSHELL' || true
[Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
POWERSHELL
    architecture="$(remote_powershell "$architecture_script" | tr -d '\r\n')"
    case "$architecture" in
        Arm64) requested_rid=win-arm64 ;;
        X64) requested_rid=win-x64 ;;
        *)
            printf 'Unsupported Windows architecture: %s\n' "$architecture" >&2
            exit 1
            ;;
    esac
fi
readonly runtime_id="$requested_rid"
readonly bootstrap_profile="$profile"

"$repo_root/scripts/publish-windows.sh" "$runtime_id"

readonly publish_root="$repo_root/publish/$runtime_id"
readonly manifest="$publish_root/providers/cua/provider.json"
readonly provider_executable="$publish_root/providers/cua/cua-driver.exe"
readonly provider_license="$publish_root/providers/cua/LICENSE.md"
for required_path in \
    "$publish_root/machine-control-windows.exe" \
    "$publish_root/PenImc_cor3.dll" \
    "$publish_root/PresentationNative_cor3.dll" \
    "$publish_root/vcruntime140_cor3.dll" \
    "$publish_root/wpfgfx_cor3.dll" \
    "$manifest" \
    "$provider_executable" \
    "$provider_license"; do
    if [[ ! -f "$required_path" ]]; then
        printf 'Published package is incomplete: %s\n' "$required_path" >&2
        exit 1
    fi
done

expected_digest="$(jq -er --arg rid "$runtime_id" \
    '.windows[$rid].executableSha256' "$manifest")"
actual_digest="$(shasum -a 256 "$provider_executable" | awk '{print $1}')"
if [[ "$actual_digest" != "$expected_digest" ]]; then
    printf 'Published Cua executable digest does not match its manifest.\n' >&2
    exit 1
fi
readonly runtime_digest="$(shasum -a 256 \
    "$publish_root/machine-control-windows.exe" | awk '{print $1}')"

local_stage="$(mktemp -d "${TMPDIR:-/tmp}/machine-control-bootstrap.XXXXXX")"
readonly local_stage
readonly remote_stage_name="machine-control-bootstrap-$(date -u +%Y%m%d%H%M%S)-$$"
remote_stage_created=0

cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM
    if [[ "$remote_stage_created" -eq 1 ]]; then
        local cleanup_script
        cleanup_script="\$p=Join-Path \$env:USERPROFILE '$remote_stage_name'; if(Test-Path -LiteralPath \$p){Remove-Item -LiteralPath \$p -Recurse -Force}"
        remote_powershell "$cleanup_script" >/dev/null 2>&1 || true
    fi
    if [[ -d "$local_stage" &&
        "$local_stage" == "${TMPDIR:-/tmp}/machine-control-bootstrap."* ]]; then
        rm -rf -- "$local_stage"
    fi
    exit "$exit_code"
}
trap cleanup EXIT INT TERM

readonly archive="$local_stage/runtime.zip"
if command -v ditto >/dev/null 2>&1; then
    ditto -c -k --sequesterRsrc --keepParent "$publish_root" "$archive"
else
    (
        cd "$repo_root/publish"
        zip -q -r "$archive" "$runtime_id"
    )
fi

create_stage_script="\$p=Join-Path \$env:USERPROFILE '$remote_stage_name'; if(Test-Path -LiteralPath \$p){throw 'bootstrap stage already exists'}; New-Item -ItemType Directory -Path \$p | Out-Null"
remote_powershell "$create_stage_script" >/dev/null
remote_stage_created=1

"$scp_bin" -q \
    "$archive" \
    "$repo_root/scripts/install-windows.ps1" \
    "$ssh_target:$remote_stage_name/"

read -r -d '' install_script <<'POWERSHELL' || true
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$stage = Join-Path $env:USERPROFILE '__REMOTE_STAGE__'
$archive = Join-Path $stage 'runtime.zip'
$expanded = Join-Path $stage 'expanded'
$runtimeId = '__RUNTIME_ID__'
$profile = '__BOOTSTRAP_PROFILE__'
$result = $null
try {
    Expand-Archive -LiteralPath $archive -DestinationPath $expanded
    $source = Join-Path $expanded $runtimeId
    $providerRoot = Join-Path $source 'providers\cua'
    $providerExecutable = Join-Path $providerRoot 'cua-driver.exe'
    $providerManifest = Get-Content -Raw -LiteralPath `
        (Join-Path $providerRoot 'provider.json') | ConvertFrom-Json
    $providerTarget = $providerManifest.windows.PSObject.Properties[
        $runtimeId].Value
    $expectedDigest = $providerTarget.executableSha256
    $actualDigest = (Get-FileHash -Algorithm SHA256 -LiteralPath `
        $providerExecutable).Hash.ToLowerInvariant()
    if ($actualDigest -ne $expectedDigest) {
        throw 'transferred Cua executable digest mismatch'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $providerRoot 'LICENSE.md'))) {
        throw 'transferred provider license is absent'
    }

    $development = $null
    if ($profile -eq 'development') {
        $developmentScript = Join-Path $source `
            'support\bootstrap-development.ps1'
        $developmentJson = & powershell.exe -NoLogo -NoProfile `
            -NonInteractive -ExecutionPolicy Bypass `
            -File $developmentScript | Out-String
        if ($LASTEXITCODE -ne 0) {
            throw 'development tool bootstrap failed'
        }
        $development = $developmentJson | ConvertFrom-Json
        if (-not $development.healthy) {
            throw 'development tool verification failed'
        }
    }

    $installer = Join-Path $stage 'install-windows.ps1'
    $null = & powershell.exe -NoLogo -NoProfile -NonInteractive `
        -ExecutionPolicy Bypass -File $installer -SourceDirectory $source
    if ($LASTEXITCODE -ne 0) {
        throw "installer exited with $LASTEXITCODE"
    }
    $service = Get-CimInstance Win32_Service -Filter `
        "Name='MachineControlRuntime'"
    if (-not $service -or $service.State -ne 'Running' -or
        $service.StartMode -ne 'Auto' -or $service.StartName -ne 'LocalSystem') {
        throw 'installed service did not reach the required automatic state'
    }

    $executable = Join-Path $env:ProgramData `
        'MachineControl\runtime\machine-control-windows.exe'
    $runtimeDigest = (Get-FileHash -Algorithm SHA256 -LiteralPath `
        $executable).Hash.ToLowerInvariant()
    if ($runtimeDigest -ne '__RUNTIME_DIGEST__') {
        throw 'installed runtime executable digest mismatch'
    }
    foreach ($companion in @(
        'PenImc_cor3.dll',
        'PresentationNative_cor3.dll',
        'vcruntime140_cor3.dll',
        'wpfgfx_cor3.dll')) {
        if (-not (Test-Path -LiteralPath `
                (Join-Path (Split-Path $executable) $companion))) {
            throw "installed native companion is absent: $companion"
        }
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        $status = '{"operation":"status"}' | & $executable call |
            ConvertFrom-Json
        if ($status.accepted -and $status.desktop -eq 'Default' -and
            -not $status.data.isLocalSystem -and
            $status.data.integrityRid -eq 8192) {
            break
        }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)
    if (-not $status.accepted -or $status.desktop -ne 'Default' -or
        $status.data.isLocalSystem -or $status.data.integrityRid -ne 8192) {
        throw 'Medium interactive helper did not become ready'
    }

    $capabilities = '{"operation":"capabilities"}' | & $executable call |
        ConvertFrom-Json
    $cua = @($capabilities.data.providers |
        Where-Object { $_.id -eq 'cua' } | Select-Object -First 1)
    $native = @($capabilities.data.providers |
        Where-Object { $_.id -eq 'windows-native' } | Select-Object -First 1)
    if (-not $capabilities.accepted -or $cua.Count -ne 1 -or
        $native.Count -ne 1 -or
        $cua[0].state -notin @('experimental', 'native') -or
        $native[0].state -ne 'native') {
        throw 'installed provider inventory is not ready'
    }

    $result = [ordered]@{
        schema = 'machine-control-bootstrap/v0'
        installed = $true
        profile = $profile
        development = $development
        runtime_id = $runtimeId
        service_state = $service.State
        service_start_mode = $service.StartMode
        service_identity = $service.StartName
        desktop = $status.desktop
        helper_integrity_rid = $status.data.integrityRid
        cua_state = $cua[0].state
        cua_version = $cua[0].version
        native_state = $native[0].state
        provider_digest = $actualDigest
        runtime_digest = $runtimeDigest
        staging_removed = $true
    }
}
finally {
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}
$result | ConvertTo-Json -Compress -Depth 10
POWERSHELL
install_script="${install_script//__REMOTE_STAGE__/$remote_stage_name}"
install_script="${install_script//__RUNTIME_ID__/$runtime_id}"
install_script="${install_script//__BOOTSTRAP_PROFILE__/$bootstrap_profile}"
install_script="${install_script//__RUNTIME_DIGEST__/$runtime_digest}"
remote_powershell "$install_script"
remote_stage_created=0
