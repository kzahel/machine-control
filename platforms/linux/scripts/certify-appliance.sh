#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly LINUXVM="${LINUXVM_CERTIFY_LINUXVM:-$LINUXVM_REPO_DIR/bin/linuxvm}"
readonly ROOT_DIR="$(cd "$LINUXVM_REPO_DIR/../.." && pwd)"

usage() {
    cat <<'EOF'
Usage: linuxvm appliance-certify [--profile development|runtime] [--json]

Certifies exact committed source on the exact retained Linux candidate. The
command performs no repair and creates no clone or workspace. It reboots, runs
portable and Linux-native checks, removes staging, and shuts down on success.
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
        --help|-h) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

check_timeout="${LINUXVM_CERTIFY_CHECK_TIMEOUT:-1200}"
if [[ ! "$check_timeout" =~ ^[0-9]+$ ||
      "$check_timeout" -lt 60 || "$check_timeout" -gt 3600 ]]; then
    printf 'LINUXVM_CERTIFY_CHECK_TIMEOUT must be 60-3600 seconds.\n' >&2
    exit 2
fi

for tool in git jq shasum; do linuxvm_require_command "$tool"; done
if [[ "${LINUXVM_CERTIFY_ALLOW_DIRTY_FOR_TESTS:-0}" != 1 &&
      -n "$(git -C "$ROOT_DIR" status --porcelain --untracked-files=normal)" ]]; then
    printf 'Appliance certification requires a clean committed source tree.\n' >&2
    exit 1
fi

linuxvm_assert_candidate_target
if [[ "$($LINUXVM status 2>/dev/null || true)" != started ]]; then
    "$LINUXVM" up >/dev/null
fi

initial_audit="$($LINUXVM post-update audit --profile "$profile" --json)"
if ! jq -e '.healthy == true and .post_update.healthy == true and
        .doctor.ready == true' <<<"$initial_audit" >/dev/null; then
    printf 'Initial post-update audit is unhealthy; certification will not repair it.\n' >&2
    exit 1
fi

"$LINUXVM" reboot >/dev/null
reboot_audit=""
deadline=$((SECONDS + LINUXVM_BOOT_TIMEOUT))
while (( SECONDS < deadline )); do
    reboot_audit="$($LINUXVM post-update audit --profile "$profile" \
        --json 2>/dev/null || true)"
    if jq -e '.healthy == true and .post_update.healthy == true and
            .doctor.ready == true' <<<"$reboot_audit" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
if ! jq -e '.healthy == true and .post_update.healthy == true and
        .doctor.ready == true' <<<"$reboot_audit" >/dev/null 2>&1; then
    printf 'Certification did not regain readiness after the observed reboot.\n' >&2
    exit 1
fi

revision="$(git -C "$ROOT_DIR" rev-parse HEAD)"
temp_root="${TMPDIR:-/tmp}"
temp_root="${temp_root%/}"
local_stage="$(mktemp -d "$temp_root/machine-control-linux-certify.XXXXXX")"
remote_stage="/var/tmp/machine-control-certify-${revision:0:12}-$$"
remote_created=false

cleanup_remote() {
    if [[ "$remote_created" == true &&
          "$remote_stage" =~ ^/var/tmp/machine-control-certify-[0-9a-f]{12}-[0-9]+$ ]]; then
        if "$LINUXVM" exec -- /usr/bin/rm -rf -- "$remote_stage" \
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
          "$local_stage" == "$temp_root/machine-control-linux-certify."* ]]; then
        rm -rf -- "$local_stage"
    fi
    exit "$exit_code"
}
trap cleanup EXIT INT TERM

archive="$local_stage/source.tar.gz"
git -C "$ROOT_DIR" archive --format=tar.gz --output="$archive" HEAD
source_digest="$(shasum -a 256 "$archive" | awk '{print $1}')"

"$LINUXVM" exec -- /usr/bin/install -d -m 0700 "$remote_stage"
remote_created=true
"$LINUXVM" push "$archive" "$remote_stage/source.tar.gz"
if ! "$LINUXVM" exec -- /usr/bin/bash -lc \
        'set -euo pipefail; stage="$1"; expected="$2"; actual="$(sha256sum "$stage/source.tar.gz")"; actual="${actual%% *}"; test "$actual" = "$expected"; mkdir "$stage/source"; tar -xzf "$stage/source.tar.gz" -C "$stage/source"' \
        _ "$remote_stage" "$source_digest" >/dev/null; then
    staging_removed=false
    if cleanup_remote; then staging_removed=true; fi
    jq -cn --argjson removed "$staging_removed" '{
        schema:"machine-control-linux-appliance-certification/v0",
        healthy:false,failed_stage:"source_digest_or_extract",
        guest_checks:null,staging_removed:$removed,final_power:"running"
    }'
    exit 1
fi

run_guest_check() {
    local kind="$1" status
    set +e
    LINUXVM_EXEC_TIMEOUT=$((check_timeout + 30)) "$LINUXVM" exec -- \
        /usr/bin/bash -lc \
        'stage="$1"; timeout="$2"; kind="$3"; cd "$stage/source"; exec /usr/bin/timeout --signal=TERM --kill-after=10s "${timeout}s" /usr/bin/python3 bin/check "--$kind" >"$stage/$kind.out.log" 2>"$stage/$kind.err.log"' \
        _ "$remote_stage" "$check_timeout" "$kind" >/dev/null
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
else
    if [[ "$LAST_GUEST_CHECK_STATUS" -eq 124 ]]; then
        failure=portable_checks_timeout
    else
        failure=portable_checks_failed
    fi
fi
if [[ "$failure" == null ]]; then
    if run_guest_check native; then
        native=passed
    else
        if [[ "$LAST_GUEST_CHECK_STATUS" -eq 124 ]]; then
            failure=native_checks_timeout
        else
            failure=native_checks_failed
        fi
    fi
fi

staging_removed=false
if cleanup_remote; then staging_removed=true; fi
guest="$(jq -cn --arg portable "$portable" --arg native "$native" \
    --arg failure "$failure" --argjson removed "$staging_removed" \
    --argjson healthy "$([[ "$failure" == null && "$staging_removed" == true ]] && printf true || printf false)" '{
        schema:"machine-control-linux-appliance-guest-certification/v0",
        healthy:$healthy,
        source_digest_match:true,
        portable_checks:$portable,
        native_checks:$native,
        staging_removed:$removed,
        failure:(if $failure == "null" then null else $failure end)
    }')"

if ! jq -e '.healthy == true' <<<"$guest" >/dev/null; then
    jq -cn --argjson guest "$guest" '{
        schema:"machine-control-linux-appliance-certification/v0",
        healthy:false,failed_stage:"guest_checks",guest_checks:$guest,
        final_power:"running"
    }'
    exit 1
fi

"$LINUXVM" shutdown >/dev/null
if [[ "$($LINUXVM status 2>/dev/null || true)" != stopped ]]; then
    printf 'Checks passed, but the Linux candidate did not cleanly stop.\n' >&2
    exit 1
fi

jq -cn --arg profile "$profile" --arg revision "$revision" \
    --arg digest "$source_digest" --argjson initial "$initial_audit" \
    --argjson rebooted "$reboot_audit" --argjson guest "$guest" '{
        schema:"machine-control-linux-appliance-certification/v0",
        healthy:true,
        profile:$profile,
        source:{revision:$revision,archive_sha256:$digest},
        reboot:{changedBootIdObserved:true,initial:$initial,final:$rebooted},
        guest_checks:$guest,
        final_power:"off"
    }'
