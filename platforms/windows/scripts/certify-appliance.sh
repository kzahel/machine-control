#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly WINVM="${WINVM_CERTIFY_WINVM:-$WINVM_REPO_DIR/bin/winvm}"
readonly ROOT_DIR="$(cd "$WINVM_REPO_DIR/../.." && pwd)"

certification_ready() {
    local value doctor
    value="$(cat)"
    jq -e '.healthy == true and .post_update.healthy == true and
        (.doctor | type) == "object"' <<<"$value" >/dev/null || return
    doctor="$(jq -c '.doctor' <<<"$value")"
    winvm_doctor_appliance_ready <<<"$doctor"
}

usage() {
    cat <<'EOF'
Usage: winvm appliance-certify [--profile development|runtime] [--json]

Certifies the exact clean committed source on the exact Windows candidate.
The command performs no repair and creates no clone or workspace. It reboots,
runs portable and Windows-native checks, removes staging, and cleanly shuts
down only after every acceptance check passes.
EOF
}

profile=development
while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)
            if [[ $# -lt 2 ||
                ( "$2" != development && "$2" != runtime ) ]]; then
                usage >&2
                exit 2
            fi
            profile="$2"
            shift 2
            ;;
        --json)
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            usage >&2
            exit 2
            ;;
    esac
done

if [[ ! "$WINVM_CERTIFY_CHECK_TIMEOUT" =~ ^[0-9]+$ ||
    "$WINVM_CERTIFY_CHECK_TIMEOUT" -lt 60 ||
    "$WINVM_CERTIFY_CHECK_TIMEOUT" -gt 3600 ]]; then
    printf 'WINVM_CERTIFY_CHECK_TIMEOUT must be 60-3600 seconds.\n' >&2
    exit 2
fi
readonly check_timeout_ms=$((WINVM_CERTIFY_CHECK_TIMEOUT * 1000))

for tool in git jq shasum iconv base64 "$WINVM_SSH_BIN" "$WINVM_SCP_BIN"; do
    winvm_require_command "$tool"
done

if [[ "${WINVM_CERTIFY_ALLOW_DIRTY_FOR_TESTS:-0}" != 1 &&
    -n "$(git -C "$ROOT_DIR" status --porcelain --untracked-files=normal)" ]]; then
    printf 'Appliance certification requires a clean committed source tree.\n' >&2
    exit 1
fi

"$WINVM" assert-target appliance-certify >/dev/null
if [[ "$($WINVM status 2>/dev/null || true)" != started ]]; then
    "$WINVM" up >/dev/null
fi

initial_audit="$($WINVM post-update audit --profile "$profile" --json)"
if ! certification_ready <<<"$initial_audit" >/dev/null; then
    printf 'Initial post-update audit is not healthy; certification will not repair it.\n' >&2
    exit 1
fi
initial_epoch="$(jq -er '.post_update.boot_epoch_utc' <<<"$initial_audit")"

"$WINVM_SSH_BIN" -o BatchMode=yes -o ConnectTimeout=10 \
    "$WINVM_SSH_HOST" 'shutdown.exe /r /t 0' >/dev/null 2>&1 || true

reboot_audit=""
deadline=$((SECONDS + WINVM_BOOT_TIMEOUT))
while (( SECONDS < deadline )); do
    reboot_audit="$($WINVM post-update audit --profile "$profile" \
        --json 2>/dev/null || true)"
    if certification_ready <<<"$reboot_audit" >/dev/null 2>&1 &&
        jq -e --arg epoch "$initial_epoch" \
            '.post_update.boot_epoch_utc != $epoch' \
            <<<"$reboot_audit" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
if ! certification_ready <<<"$reboot_audit" >/dev/null 2>&1 ||
    ! jq -e --arg epoch "$initial_epoch" \
        '.post_update.boot_epoch_utc != $epoch' \
        <<<"$reboot_audit" >/dev/null 2>&1; then
    printf 'Certification did not observe healthy readiness after a changed boot epoch.\n' >&2
    exit 1
fi

revision="$(git -C "$ROOT_DIR" rev-parse HEAD)"
local_stage="$(mktemp -d "${TMPDIR:-/tmp}/machine-control-certify.XXXXXX")"
readonly local_stage revision
remote_stage_name="machine-control-certify-${revision:0:12}-$$"
readonly remote_stage_name
remote_stage_created=0

remote_powershell() {
    local script="$1" encoded output status
    encoded="$(printf '%s' "$script" | winvm_encode_powershell)"
    set +e
    output="$($WINVM_SSH_BIN -o BatchMode=yes -o ConnectTimeout=15 \
        "$WINVM_SSH_HOST" \
        "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand $encoded" \
        2>/dev/null)"
    status=$?
    set -e
    printf '%s' "$output"
    return "$status"
}

cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM
    if [[ "$remote_stage_created" -eq 1 ]]; then
        local cleanup_script
        cleanup_script="\$p=Join-Path \$env:USERPROFILE '$remote_stage_name'; if(Test-Path -LiteralPath \$p){Remove-Item -LiteralPath \$p -Recurse -Force}"
        remote_powershell "$cleanup_script" >/dev/null 2>&1 || true
    fi
    if [[ -d "$local_stage" &&
        "$local_stage" == "${TMPDIR:-/tmp}/machine-control-certify."* ]]; then
        rm -rf -- "$local_stage"
    fi
    exit "$exit_code"
}
trap cleanup EXIT INT TERM

archive="$local_stage/source.zip"
git -C "$ROOT_DIR" archive --format=zip --output="$archive" HEAD
source_digest="$(shasum -a 256 "$archive" | awk '{print $1}')"
readonly archive source_digest

create_stage="\$p=Join-Path \$env:USERPROFILE '$remote_stage_name'; if(Test-Path -LiteralPath \$p){throw 'certification stage already exists'}; New-Item -ItemType Directory -Path \$p | Out-Null"
remote_powershell "$create_stage" >/dev/null
remote_stage_created=1
"$WINVM_SCP_BIN" -q "$archive" \
    "$WINVM_SSH_HOST:$remote_stage_name/source.zip"

read -r -d '' guest_checks <<'POWERSHELL' || true
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$stage = Join-Path $env:USERPROFILE '__REMOTE_STAGE__'
$archive = Join-Path $stage 'source.zip'
$source = Join-Path $stage 'source'
$result = [ordered]@{
    schema = 'machine-control-windows-appliance-guest-certification/v0'
    healthy = $false
    source_digest_match = $false
    portable_checks = 'not_run'
    native_checks = 'not_run'
    staging_removed = $false
    failure = $null
}
function Stop-CheckTree {
    param([Parameter(Mandatory = $true)]$Process)
    try {
        $killer = Start-Process -FilePath taskkill.exe `
            -ArgumentList @('/PID', "$($Process.Id)", '/T', '/F') `
            -Wait -PassThru -WindowStyle Hidden
        if ($killer.ExitCode -ne 0) { throw 'taskkill failed' }
    }
    catch {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }
    [void]$Process.WaitForExit(10000)
}
try {
    $result.failure = 'source_digest_failed'
    $digest = (Get-FileHash -Algorithm SHA256 `
        -LiteralPath $archive).Hash.ToLowerInvariant()
    if ($digest -ne '__SOURCE_DIGEST__') {
        $result.failure = 'source_digest_mismatch'
        throw 'digest mismatch'
    }
    $result.source_digest_match = $true
    $result.failure = 'archive_expand_failed'
    Expand-Archive -LiteralPath $archive -DestinationPath $source
    $result.failure = 'source_entry_failed'
    $python = (Get-Command py.exe -ErrorAction Stop).Source
    $result.failure = 'portable_execution_failed'
    $portable = Start-Process -FilePath $python `
        -ArgumentList @('-3', 'bin\check', '--portable') `
        -WorkingDirectory $source -PassThru -NoNewWindow `
        -RedirectStandardOutput (Join-Path $stage 'portable.out.log') `
        -RedirectStandardError (Join-Path $stage 'portable.err.log')
    if (-not $portable.WaitForExit(__CHECK_TIMEOUT_MS__)) {
        Stop-CheckTree -Process $portable
        $result.failure = 'portable_checks_timeout'
        throw 'portable checks timed out'
    }
    # Timed WaitForExit does not complete asynchronous redirected-stream
    # handling. Finish that drain before reading the final process exit code.
    $portable.WaitForExit()
    $portable.Refresh()
    if ($portable.ExitCode -ne 0) {
        $result.failure = 'portable_checks_failed'
        throw 'portable checks failed'
    }
    $result.portable_checks = 'passed'
    $result.failure = 'native_execution_failed'
    $native = Start-Process -FilePath $python `
        -ArgumentList @('-3', 'bin\check', '--native') `
        -WorkingDirectory $source -PassThru -NoNewWindow `
        -RedirectStandardOutput (Join-Path $stage 'native.out.log') `
        -RedirectStandardError (Join-Path $stage 'native.err.log')
    if (-not $native.WaitForExit(__CHECK_TIMEOUT_MS__)) {
        Stop-CheckTree -Process $native
        $result.failure = 'native_checks_timeout'
        throw 'native checks timed out'
    }
    $native.WaitForExit()
    $native.Refresh()
    if ($native.ExitCode -ne 0) {
        $result.failure = 'native_checks_failed'
        throw 'native checks failed'
    }
    $result.native_checks = 'passed'
    $result.healthy = $true
    $result.failure = $null
}
catch {
    if (-not $result.failure) { $result.failure = 'guest_execution_failed' }
}
finally {
    Remove-Item -LiteralPath $stage -Recurse -Force `
        -ErrorAction SilentlyContinue
    $result.staging_removed = -not (Test-Path -LiteralPath $stage)
}
$result | ConvertTo-Json -Compress
if (-not $result.healthy -or -not $result.staging_removed) { exit 1 }
POWERSHELL
guest_checks="${guest_checks//__REMOTE_STAGE__/$remote_stage_name}"
guest_checks="${guest_checks//__SOURCE_DIGEST__/$source_digest}"
guest_checks="${guest_checks//__CHECK_TIMEOUT_MS__/$check_timeout_ms}"
set +e
guest_result="$(remote_powershell "$guest_checks")"
guest_status=$?
set -e
guest_result="$(printf '%s\n' "$guest_result" | tr -d '\r' | tail -n 1)"
if jq -e '.staging_removed == true' <<<"$guest_result" \
        >/dev/null 2>&1; then
    remote_stage_created=0
fi
if ! jq -e '.schema ==
        "machine-control-windows-appliance-guest-certification/v0" and
        .healthy == true and .source_digest_match == true and
        .portable_checks == "passed" and .native_checks == "passed" and
        .staging_removed == true' <<<"$guest_result" >/dev/null 2>&1; then
    if jq -e '.schema ==
            "machine-control-windows-appliance-guest-certification/v0"' \
            <<<"$guest_result" >/dev/null 2>&1; then
        jq -cn --argjson guest "$guest_result" '{
            schema:"machine-control-windows-appliance-certification/v0",
            healthy:false,
            failed_stage:"guest_checks",
            guest_checks:$guest,
            final_power:"running"
        }'
    else
        jq -cn --arg status "$guest_status" '{
            schema:"machine-control-windows-appliance-certification/v0",
            healthy:false,
            failed_stage:"guest_report",
            guest_status:$status,
            final_power:"running"
        }'
    fi
    exit 1
fi

"$WINVM" shutdown >/dev/null
if [[ "$($WINVM status 2>/dev/null || true)" != stopped ]]; then
    printf 'All guest checks passed, but the candidate did not cleanly stop.\n' >&2
    exit 1
fi

jq -cn \
    --arg profile "$profile" \
    --arg revision "$revision" \
    --arg sourceDigest "$source_digest" \
    --argjson initial "$initial_audit" \
    --argjson rebooted "$reboot_audit" \
    --argjson guest "$guest_result" \
    '{
        schema:"machine-control-windows-appliance-certification/v0",
        healthy:true,
        profile:$profile,
        source:{revision:$revision,archive_sha256:$sourceDigest},
        reboot:{observed:true,initial:$initial,final:$rebooted},
        guest_checks:$guest,
        final_power:"off"
    }'
