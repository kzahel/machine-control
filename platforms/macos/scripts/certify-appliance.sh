#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly MACVM="${MACVM_CERTIFY_MACVM:-$MACVM_REPO_DIR/bin/macvm}"
readonly ROOT_DIR="$(cd "$MACVM_REPO_DIR/../.." && pwd)"

usage() {
    cat <<'EOF'
Usage: macvm appliance-certify [--profile development|runtime] [--json]

Certifies exact clean committed source on the exact retained macOS candidate.
The command does not repair, clone, or acquire a workspace. It observes a real
reboot, runs portable and macOS-native checks, cleans staging, and shuts down
only after success.
EOF
}

profile=development
while (( $# > 0 )); do
    case "$1" in
        --profile)
            if (( $# < 2 )) ||
                    [[ "$2" != development && "$2" != runtime ]]; then
                usage >&2
                exit 2
            fi
            profile="$2"
            shift 2
            ;;
        --json) shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

if [[ ! "$MACVM_CERTIFY_CHECK_TIMEOUT" =~ ^[0-9]+$ ||
      "$MACVM_CERTIFY_CHECK_TIMEOUT" -lt 60 ||
      "$MACVM_CERTIFY_CHECK_TIMEOUT" -gt 3600 ]]; then
    printf 'MACVM_CERTIFY_CHECK_TIMEOUT must be 60-3600 seconds.\n' >&2
    exit 2
fi
for tool in git jq shasum; do macvm_require_command "$tool"; done
if [[ "${MACVM_CERTIFY_ALLOW_DIRTY_FOR_TESTS:-0}" != 1 &&
      -n "$(git -C "$ROOT_DIR" status --porcelain --untracked-files=normal)" ]]; then
    printf 'Appliance certification requires a clean committed source tree.\n' >&2
    exit 1
fi

macvm_assert_candidate_target
assertion="$($MACVM candidate-status --json)"
if ! jq -e '.schema == "machine-control-candidate-assertion/v0" and
        .identityPin == "verified" and .role == "candidate" and
        .workspaceOwnership == "clear"' <<<"$assertion" >/dev/null; then
    printf 'Appliance certification requires an unowned exact candidate.\n' >&2
    exit 1
fi
if [[ "$($MACVM status 2>/dev/null || true)" != running ]]; then
    "$MACVM" up >/dev/null
fi

initial_audit="$($MACVM post-update audit --profile "$profile" --json)"
if ! jq -e '.healthy == true and .post_update.healthy == true and
        .doctor.ready == true' <<<"$initial_audit" >/dev/null; then
    printf 'Initial post-update audit is unhealthy; certification will not repair it.\n' \
        >&2
    exit 1
fi

guest_boot_epoch() {
    local value
    value="$($MACVM exec /usr/sbin/sysctl -n kern.boottime 2>/dev/null)" || return
    if [[ "$value" =~ sec[[:space:]]*=[[:space:]]*([0-9]+) ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
        return 0
    fi
    return 1
}

initial_epoch="$(guest_boot_epoch)"
"$MACVM" exec /usr/bin/sudo -n /sbin/shutdown -r now \
    >/dev/null 2>&1 || true
reboot_audit=""
changed_epoch=false
deadline=$((SECONDS + MACVM_BOOT_TIMEOUT))
while (( SECONDS < deadline )); do
    current_epoch="$(guest_boot_epoch 2>/dev/null || true)"
    if [[ -n "$current_epoch" && "$current_epoch" != "$initial_epoch" ]]; then
        changed_epoch=true
        reboot_audit="$($MACVM post-update audit --profile "$profile" \
            --json 2>/dev/null || true)"
        if jq -e '.healthy == true and .post_update.healthy == true and
                .doctor.ready == true' <<<"$reboot_audit" >/dev/null 2>&1; then
            break
        fi
    fi
    sleep 2
done
if [[ "$changed_epoch" != true ]] ||
        ! jq -e '.healthy == true and .post_update.healthy == true and
            .doctor.ready == true' <<<"$reboot_audit" >/dev/null 2>&1; then
    printf 'Certification did not regain readiness after a changed boot epoch.\n' \
        >&2
    exit 1
fi

revision="$(git -C "$ROOT_DIR" rev-parse HEAD)"
temp_root="${TMPDIR:-/tmp}"
temp_root="${temp_root%/}"
local_stage="$(mktemp -d "$temp_root/machine-control-macos-certify.XXXXXX")"
remote_stage="/private/tmp/machine-control-certify-${revision:0:12}-$$"
remote_created=false

cleanup_remote() {
    if [[ "$remote_created" == true &&
          "$remote_stage" =~ ^/private/tmp/machine-control-certify-[0-9a-f]{12}-[0-9]+$ ]]; then
        if "$MACVM" exec /bin/rm -rf -- "$remote_stage" \
                >/dev/null 2>&1; then
            remote_created=false
            return 0
        fi
        return 1
    fi
}

cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM
    cleanup_remote || true
    if [[ -d "$local_stage" &&
          "$local_stage" == "$temp_root/machine-control-macos-certify."* ]]; then
        rm -rf -- "$local_stage"
    fi
    exit "$exit_code"
}
trap cleanup EXIT INT TERM

archive="$local_stage/source.tar.gz"
git -C "$ROOT_DIR" archive --format=tar.gz --output="$archive" HEAD
source_digest="$(shasum -a 256 "$archive" | awk '{print $1}')"

"$MACVM" exec /usr/bin/install -d -m 0700 "$remote_stage"
remote_created=true
"$MACVM" exec -i /usr/bin/tee "$remote_stage/source.tar.gz" \
    <"$archive" >/dev/null
if ! "$MACVM" exec /bin/bash -c \
        'set -euo pipefail; stage="$1"; expected="$2"; actual="$(/usr/bin/shasum -a 256 "$stage/source.tar.gz")"; actual="${actual%% *}"; test "$actual" = "$expected"; /bin/mkdir "$stage/source"; /usr/bin/tar -xzf "$stage/source.tar.gz" -C "$stage/source"' \
        _ "$remote_stage" "$source_digest" >/dev/null; then
    staging_removed=false
    if cleanup_remote; then staging_removed=true; fi
    jq -cn --argjson removed "$staging_removed" '{
        schema:"machine-control-macos-appliance-certification/v0",
        healthy:false,failed_stage:"source_digest_or_extract",
        guest_checks:null,staging_removed:$removed,final_power:"running"
    }'
    exit 1
fi

read -r -d '' python_runner <<'PYTHON' || true
import os
from pathlib import Path
import signal
import subprocess
import sys

source = Path(sys.argv[1])
kind = sys.argv[2]
timeout = int(sys.argv[3])
home = Path(sys.argv[4])
stdout_path = Path(sys.argv[5])
stderr_path = Path(sys.argv[6])
home.mkdir(parents=True, exist_ok=True)
environment = {
    **os.environ,
    "HOME": str(home),
    "XDG_STATE_HOME": str(home / ".local" / "state"),
    "PYTHONDONTWRITEBYTECODE": "1",
}
with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
    process = subprocess.Popen(
        [sys.executable, "bin/check", f"--{kind}"],
        cwd=source,
        env=environment,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
    )
    try:
        raise SystemExit(process.wait(timeout=timeout))
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        raise SystemExit(124)
PYTHON

run_guest_check() {
    local kind="$1" status
    set +e
    "$MACVM" exec /usr/bin/python3 -c "$python_runner" \
        "$remote_stage/source" "$kind" "$MACVM_CERTIFY_CHECK_TIMEOUT" \
        "$remote_stage/home" "$remote_stage/$kind.out.log" \
        "$remote_stage/$kind.err.log" >/dev/null
    status=$?
    set -e
    LAST_GUEST_CHECK_STATUS="$status"
    return "$status"
}

portable=not_run
native=not_run
failure=null
if run_guest_check portable; then
    portable=passed
elif [[ "$LAST_GUEST_CHECK_STATUS" -eq 124 ]]; then
    failure=portable_checks_timeout
else
    failure=portable_checks_failed
fi
if [[ "$failure" == null ]]; then
    if run_guest_check native; then
        native=passed
    elif [[ "$LAST_GUEST_CHECK_STATUS" -eq 124 ]]; then
        failure=native_checks_timeout
    else
        failure=native_checks_failed
    fi
fi

staging_removed=false
if cleanup_remote; then staging_removed=true; fi
guest="$(jq -cn --arg portable "$portable" --arg native "$native" \
    --arg failure "$failure" --argjson removed "$staging_removed" \
    --argjson healthy "$([[ "$failure" == null && "$staging_removed" == true ]] && printf true || printf false)" '{
        schema:"machine-control-macos-appliance-guest-certification/v0",
        healthy:$healthy,source_digest_match:true,
        portable_checks:$portable,native_checks:$native,
        staging_removed:$removed,
        failure:(if $failure == "null" then null else $failure end)
    }')"

if ! jq -e '.healthy == true' <<<"$guest" >/dev/null; then
    jq -cn --argjson guest "$guest" '{
        schema:"machine-control-macos-appliance-certification/v0",
        healthy:false,failed_stage:"guest_checks",guest_checks:$guest,
        final_power:"running"
    }'
    exit 1
fi

"$MACVM" shutdown >/dev/null
if [[ "$($MACVM status 2>/dev/null || true)" != stopped ]]; then
    printf 'Checks passed, but the macOS candidate did not cleanly stop.\n' >&2
    exit 1
fi

jq -cn --arg profile "$profile" --arg revision "$revision" \
    --arg digest "$source_digest" --argjson initial "$initial_audit" \
    --argjson rebooted "$reboot_audit" --argjson guest "$guest" '{
        schema:"machine-control-macos-appliance-certification/v0",
        healthy:true,profile:$profile,
        source:{revision:$revision,archive_sha256:$digest},
        reboot:{changedBootEpochObserved:true,initial:$initial,final:$rebooted},
        guest_checks:$guest,final_power:"off"
    }'
