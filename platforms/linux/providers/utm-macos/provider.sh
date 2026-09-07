#!/usr/bin/env bash

set -euo pipefail

readonly PROVIDER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../scripts/common.sh
source "$PROVIDER_DIR/../../scripts/common.sh"

usage() {
    cat <<'EOF'
Usage: provider.sh COMMAND [ARG...]

Internal UTM-on-macOS provider. Use bin/linuxvm instead.
EOF
}

require_utmctl() {
    if [[ "$(uname -s)" != "Darwin" ]]; then
        printf 'The utm-macos provider requires macOS\n' >&2
        exit 1
    fi
    if [[ ! -x "$LINUXVM_UTMCTL" ]]; then
        printf 'UTM CLI not found at %s\n' "$LINUXVM_UTMCTL" >&2
        exit 1
    fi
}

vm_status() {
    "$LINUXVM_UTMCTL" status "$LINUXVM_UTM_NAME" 2>/dev/null
}

ensure_running() {
    local status
    status="$(vm_status || true)"
    if [[ "$status" != "started" ]]; then
        linuxvm_assert_mutation_target
        "$LINUXVM_UTMCTL" start "$LINUXVM_UTM_NAME" >/dev/null
    fi

    local deadline=$((SECONDS + LINUXVM_BOOT_TIMEOUT))
    while (( SECONDS < deadline )); do
        status="$(vm_status || true)"
        if [[ "$status" == "started" ]]; then
            return 0
        fi
        sleep 1
    done

    printf 'Timed out waiting for UTM VM %s (last status: %s)\n' \
        "$LINUXVM_UTM_NAME" "$status" >&2
    return 1
}

guest_agent_ready() {
    "$LINUXVM_UTMCTL" exec "$LINUXVM_UTM_NAME" \
        --cmd /usr/bin/id >/dev/null 2>&1
}

wait_for_guest_agent() {
    ensure_running
    local deadline=$((SECONDS + LINUXVM_BOOT_TIMEOUT))
    while (( SECONDS < deadline )); do
        if guest_agent_ready; then
            return 0
        fi
        sleep 1
    done
    printf 'QEMU guest agent is unavailable in %s; see docs/bootstrap.md\n' \
        "$LINUXVM_UTM_NAME" >&2
    return 1
}

wait_for_vm_state() {
    local expected="$1" timeout="$2"
    local deadline=$((SECONDS + timeout)) status="unknown"
    while (( SECONDS < deadline )); do
        status="$(vm_status || true)"
        if [[ "$status" == "$expected" ]]; then
            return 0
        fi
        sleep 1
    done
    LAST_VM_STATUS="$status"
    return 1
}

guest_shutdown() {
    linuxvm_assert_mutation_target
    local status
    status="$(vm_status || true)"
    if [[ "$status" == "stopped" ]]; then
        printf 'stopped\n'
        return
    fi
    if [[ "$status" == "unknown" || -z "$status" ]]; then
        printf 'UTM VM not found: %s\n' "$LINUXVM_UTM_NAME" >&2
        return 1
    fi

    "$LINUXVM_UTMCTL" stop --request "$LINUXVM_UTM_NAME" >/dev/null
    if wait_for_vm_state stopped "$LINUXVM_SHUTDOWN_TIMEOUT"; then
        printf 'stopped\n'
        return
    fi

    printf 'Timed out waiting for UTM VM %s to shut down (last status: %s)\n' \
        "$LINUXVM_UTM_NAME" "${LAST_VM_STATUS:-unknown}" >&2
    return 1
}

guest_ipv4() {
    ensure_running
    local deadline=$((SECONDS + LINUXVM_BOOT_TIMEOUT))
    local addresses ip
    while (( SECONDS < deadline )); do
        addresses="$("$LINUXVM_UTMCTL" ip-address \
            "$LINUXVM_UTM_NAME" 2>/dev/null || true)"
        ip="$(printf '%s\n' "$addresses" | awk \
            '/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ { print; exit }')"
        if [[ -n "$ip" ]]; then
            printf '%s\n' "$ip"
            return 0
        fi
        sleep 1
    done
    printf 'Timed out waiting for %s to report an IPv4 address\n' \
        "$LINUXVM_UTM_NAME" >&2
    return 1
}

guest_reboot() {
    linuxvm_assert_mutation_target
    wait_for_guest_agent
    local old_boot_id new_boot_id deadline
    old_boot_id="$("$LINUXVM_UTMCTL" exec "$LINUXVM_UTM_NAME" \
        --cmd /usr/bin/cat /proc/sys/kernel/random/boot_id)"
    "$LINUXVM_UTMCTL" exec "$LINUXVM_UTM_NAME" \
        --cmd /usr/bin/systemctl reboot >/dev/null 2>&1 || true

    deadline=$((SECONDS + LINUXVM_BOOT_TIMEOUT))
    while (( SECONDS < deadline )); do
        new_boot_id="$("$LINUXVM_UTMCTL" exec "$LINUXVM_UTM_NAME" \
            --cmd /usr/bin/cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)"
        if [[ -n "$new_boot_id" && "$new_boot_id" != "$old_boot_id" ]]; then
            guest_ipv4
            return 0
        fi
        sleep 2
    done
    printf 'Timed out waiting for %s to complete its reboot\n' \
        "$LINUXVM_UTM_NAME" >&2
    return 1
}

guest_exec() {
    if (( $# == 0 )); then
        printf 'Usage: linuxvm exec -- COMMAND [ARG...]\n' >&2
        return 2
    fi
    linuxvm_assert_mutation_target
    wait_for_guest_agent

    local token remote_dir remote_stdout remote_stderr remote_status
    token="$(date +%s).$$.$RANDOM"
    remote_dir="$LINUXVM_REMOTE_ROOT/run/$token"
    remote_stdout="$remote_dir/stdout"
    remote_stderr="$remote_dir/stderr"
    remote_status="$remote_dir/status"

    local quoted_command quoted_dir quoted_stdout quoted_stderr quoted_status
    printf -v quoted_command '%q ' "$@"
    printf -v quoted_dir '%q' "$remote_dir"
    printf -v quoted_stdout '%q' "$remote_stdout"
    printf -v quoted_stderr '%q' "$remote_stderr"
    printf -v quoted_status '%q' "$remote_status"

    local remote_script
    remote_script="umask 077; mkdir -p $quoted_dir; "
    remote_script+="find '$LINUXVM_REMOTE_ROOT/run' -mindepth 1 -maxdepth 1 "
    remote_script+="-type d -mmin +1440 -exec rm -rf -- {} + 2>/dev/null || true; "
    remote_script+="$quoted_command >$quoted_stdout 2>$quoted_stderr; "
    remote_script+="rc=\$?; printf '%s\\n' \"\$rc\" >$quoted_status"

    # UTM 4.7 can return from exec before a compound guest command has made
    # every side effect visible. The status file, written last, is authoritative.
    "$LINUXVM_UTMCTL" exec "$LINUXVM_UTM_NAME" \
        --cmd /usr/bin/bash -lc "$remote_script" >/dev/null 2>&1 || true

    local local_dir local_status local_stderr status deadline
    local_dir="$(mktemp -d /tmp/linuxvm-exec.XXXXXX)"
    local_status="$local_dir/status"
    local_stderr="$local_dir/stderr"
    deadline=$((SECONDS + LINUXVM_EXEC_TIMEOUT))

    while (( SECONDS < deadline )); do
        if "$LINUXVM_UTMCTL" file pull "$LINUXVM_UTM_NAME" \
            "$remote_status" >"$local_status" 2>/dev/null; then
            status="$(tr -d '\r\n' <"$local_status")"
            if [[ "$status" =~ ^[0-9]+$ ]]; then
                "$LINUXVM_UTMCTL" file pull "$LINUXVM_UTM_NAME" \
                    "$remote_stdout" 2>/dev/null || true
                if "$LINUXVM_UTMCTL" file pull "$LINUXVM_UTM_NAME" \
                    "$remote_stderr" >"$local_stderr" 2>/dev/null; then
                    cat "$local_stderr" >&2
                fi
                rm -rf "$local_dir"
                return "$status"
            fi
        fi
        sleep 1
    done

    rm -rf "$local_dir"
    printf 'Timed out after %ss waiting for guest command completion\n' \
        "$LINUXVM_EXEC_TIMEOUT" >&2
    return 124
}

guest_shell() {
    linuxvm_assert_mutation_target
    wait_for_guest_agent
    "$LINUXVM_UTMCTL" exec "$LINUXVM_UTM_NAME" --input \
        --cmd /usr/bin/bash -l
}

file_push() {
    if (( $# != 2 )); then
        printf 'Usage: linuxvm push LOCAL REMOTE\n' >&2
        return 2
    fi
    [[ -r "$1" ]] || { printf 'Unreadable local file: %s\n' "$1" >&2; return 1; }
    linuxvm_assert_mutation_target
    wait_for_guest_agent
    "$LINUXVM_UTMCTL" file push "$LINUXVM_UTM_NAME" "$2" <"$1"
}

file_pull() {
    if (( $# < 1 || $# > 2 )); then
        printf 'Usage: linuxvm pull REMOTE [LOCAL]\n' >&2
        return 2
    fi
    wait_for_guest_agent
    if (( $# == 2 )); then
        "$LINUXVM_UTMCTL" file pull "$LINUXVM_UTM_NAME" "$1" >"$2"
        printf '%s\n' "$2"
    else
        "$LINUXVM_UTMCTL" file pull "$LINUXVM_UTM_NAME" "$1"
    fi
}

input_text() {
    if (( $# != 1 )); then
        printf 'Usage: linuxvm type TEXT\n' >&2
        return 2
    fi
    /usr/bin/osascript - "$LINUXVM_UTM_NAME" "$1" <<'APPLESCRIPT'
on run argv
    tell application "UTM"
        set targetVM to first virtual machine whose name is item 1 of argv
        input keystroke targetVM text (item 2 of argv)
    end tell
end run
APPLESCRIPT
}

input_scan_codes() {
    if (( $# < 1 )); then
        printf 'Usage: linuxvm scan CODE...\n' >&2
        return 2
    fi
    local code
    for code in "$@"; do
        if [[ ! "$code" =~ ^[0-9]+$ || "$code" -gt 255 ]]; then
            printf 'Scan codes must be decimal bytes (0-255): %s\n' "$code" >&2
            return 2
        fi
    done
    /usr/bin/osascript - "$LINUXVM_UTM_NAME" "$@" <<'APPLESCRIPT'
on run argv
    set vmName to item 1 of argv
    set scanCodes to {}
    repeat with rawCode in items 2 thru -1 of argv
        set end of scanCodes to rawCode as integer
    end repeat
    tell application "UTM"
        set targetVM to first virtual machine whose name is vmName
        input scan code targetVM codes scanCodes
    end tell
end run
APPLESCRIPT
}

input_key() {
    if (( $# != 1 )); then
        printf 'Usage: linuxvm key NAME\n' >&2
        return 2
    fi
    case "$1" in
        enter)       input_scan_codes 28 156 ;;
        escape)      input_scan_codes 1 129 ;;
        tab)         input_scan_codes 15 143 ;;
        ctrl-alt-t)  input_scan_codes 29 56 20 148 184 157 ;;
        super-d)     input_scan_codes 224 91 32 160 224 219 ;;
        alt-f4)      input_scan_codes 56 62 190 184 ;;
        ctrl-alt-delete) input_scan_codes 29 56 224 83 224 211 184 157 ;;
        *) printf 'Unknown key name: %s\n' "$1" >&2; return 2 ;;
    esac
}

host_control() {
    /usr/bin/swift "$PROVIDER_DIR/host-control.swift" "$@"
}

target_id() {
    local target_name="${1:-$LINUXVM_UTM_NAME}"
    local expected_id=""
    if [[ $# -eq 0 ]]; then expected_id="$LINUXVM_EXPECTED_UUID"; fi
    /usr/bin/osascript - "$target_name" "$expected_id" <<'APPLESCRIPT'
on run argv
    set vmName to item 1 of argv
    set expectedId to item 2 of argv
    tell application "UTM"
        if expectedId is not "" then
            set targetVM to first virtual machine whose id is expectedId
        else
            set targetVM to first virtual machine whose name is vmName
        end if
        return id of targetVM
    end tell
end run
APPLESCRIPT
}

vm_is_registered() {
    "$LINUXVM_UTMCTL" status "$1" >/dev/null 2>&1
}

# Create a stopped ARM64 UTM appliance from an official Ubuntu arm64 QCOW2
# cloud image plus NoCloud seed media. The source image is never mutated: it is
# copied into ignored factory storage and expanded there before UTM imports it.
factory_create() {
    if [[ $# -ne 3 || -z "$1" || -z "$2" || -z "$3" ]]; then
        printf 'Usage: linuxvm factory-create NAME CLOUD_IMAGE SEED_ISO\n' >&2
        return 2
    fi
    local destination="$1" cloud_image="$2" seed_iso="$3" status
    for media in "$cloud_image" "$seed_iso"; do
        if [[ ! -f "$media" || ! -r "$media" ]]; then
            printf 'Factory media is absent or unreadable.\n' >&2
            return 1
        fi
    done
    linuxvm_require_command qemu-img || return 1
    cloud_image="$(cd "$(dirname "$cloud_image")" && pwd -P)/$(basename "$cloud_image")"
    seed_iso="$(cd "$(dirname "$seed_iso")" && pwd -P)/$(basename "$seed_iso")"
    if vm_is_registered "$destination"; then
        printf 'Factory destination is already registered.\n' >&2
        return 1
    fi

    local factory_root="${LINUXVM_FACTORY_LOCAL_ROOT:-$LINUXVM_REPO_DIR/.factory.local}"
    mkdir -p "$factory_root"
    chmod 700 "$factory_root"
    local system_image="$factory_root/$destination-system.qcow2"
    if [[ -e "$system_image" ]]; then
        printf 'Factory system image already exists; remove it explicitly.\n' >&2
        return 1
    fi
    if [[ "$(qemu-img info --output json "$cloud_image" | jq -r '.format')" != qcow2 ]]; then
        printf 'Cloud image must be QCOW2.\n' >&2
        return 1
    fi
    cp "$cloud_image" "$system_image"
    qemu-img resize "$system_image" 128G >/dev/null

    /usr/bin/osascript - "$destination" "$system_image" "$seed_iso" \
        >/dev/null <<'APPLESCRIPT'
on run argv
    set vmName to item 1 of argv
    set systemImage to POSIX file (item 2 of argv)
    set seedIso to POSIX file (item 3 of argv)
    tell application "UTM"
        make new virtual machine with properties {backend:qemu, configuration:{name:vmName, architecture:"aarch64", memory:4096, cpu cores:4, hypervisor:true, uefi:true, drives:{{interface:VirtIO, source:systemImage}, {removable:true, source:seedIso}}, displays:{{hardware:"virtio-ramfb-gl", dynamic resolution:true}}, network interfaces:{{mode:shared}}}}
    end tell
end run
APPLESCRIPT
    status="$("$LINUXVM_UTMCTL" status "$destination" 2>/dev/null || true)"
    if [[ "$status" != "stopped" ]]; then
        printf 'UTM did not create a stopped factory target.\n' >&2
        return 1
    fi
    factory_repair_efi_varstore "$destination" || return 1
    printf 'factory target created\n'
}

# QEMU's aarch64 `virt` machine maps two 64-MiB pflash banks, and UTM ships no
# aarch64 variable-store template. A VM created through the scripting interface
# can therefore receive an undersized efi_vars.fd, which leaves edk2 spinning
# before any boot device is examined: no guest packets, no disk writes, and no
# serial output. Normalize the bank to the size of the code image UTM pairs it
# with, keeping any correctly sized store the application already produced.
factory_repair_efi_varstore() {
    local destination="$1"
    local documents="${LINUXVM_FACTORY_UTM_DIRECTORY:-$HOME/Library/Containers/com.utmapp.UTM/Data/Documents}"
    # Factory destinations are independent of the currently configured target.
    local bundle="$documents/$destination.utm"
    local varstore="$bundle/Data/efi_vars.fd"
    local code="$HOME/Library/Containers/com.utmapp.UTM/Data/Library/Caches/qemu/edk2-aarch64-code.fd"
    if [[ ! -f "$varstore" ]]; then
        printf 'UTM did not create an EFI variable store for the new target.\n' >&2
        return 1
    fi
    local expected=67108864 actual
    if [[ -f "$code" ]]; then
        expected="$(stat -f %z "$code")"
    fi
    actual="$(stat -f %z "$varstore")"
    if [[ "$actual" == "$expected" ]]; then
        return 0
    fi
    if ! dd if=/dev/zero of="$varstore" bs=1m count=$((expected / 1048576)) \
            >/dev/null 2>&1; then
        printf 'Could not normalize the EFI variable store.\n' >&2
        return 1
    fi
    printf 'normalized EFI variable store: %s -> %s bytes\n' "$actual" "$expected" >&2
}

# Remove the stopped candidate's NoCloud seed once cloud-init has completed.
factory_detach_media() {
    local status result removed remaining
    linuxvm_assert_mutation_target || return 1
    status="$(vm_status || true)"
    if [[ "$status" != "stopped" ]]; then
        printf 'Factory media detachment requires a stopped target.\n' >&2
        return 1
    fi
    result="$(/usr/bin/osascript - "$LINUXVM_EXPECTED_UUID" <<'APPLESCRIPT'
on run argv
    set expectedId to item 1 of argv
    tell application "UTM"
        set targetVM to first virtual machine whose id is expectedId
        set vmConfig to configuration of targetVM
        set retainedDrives to {}
        set removedCount to 0
        repeat with driveConfig in drives of vmConfig
            if removable of driveConfig then
                set removedCount to removedCount + 1
            else
                set end of retainedDrives to contents of driveConfig
            end if
        end repeat
        if removedCount > 0 then
            set drives of vmConfig to retainedDrives
            update configuration targetVM with vmConfig
        end if
        set updatedConfig to configuration of targetVM
        set remainingCount to 0
        repeat with driveConfig in drives of updatedConfig
            if removable of driveConfig then
                set remainingCount to remainingCount + 1
            end if
        end repeat
        return (removedCount as text) & tab & (remainingCount as text)
    end tell
end run
APPLESCRIPT
)"
    IFS=$'\t' read -r removed remaining <<< "$result"
    if [[ ! "$removed" =~ ^[0-9]+$ || "$remaining" != "0" ]]; then
        printf 'UTM did not confirm complete removable-media detachment.\n' >&2
        return 1
    fi
    printf 'factory media detached: removed=%s remaining=0\n' "$removed"
}

guard_status() {
    local mutation_verified=false
    if [[ "$LINUXVM_REQUIRE_MUTATION_GUARD" == true ]] &&
            linuxvm_assert_mutation_target >/dev/null 2>&1; then
        mutation_verified=true
    fi
    jq -n --argjson outerUIForbidden \
        "$([[ "$LINUXVM_FORBID_OUTER_UI" == true ]] && printf true || printf false)" \
        --argjson mutationGuardRequired \
        "$([[ "$LINUXVM_REQUIRE_MUTATION_GUARD" == true ]] && printf true || printf false)" \
        --argjson mutationTargetVerified "$mutation_verified" \
        --arg targetRole "$LINUXVM_TARGET_ROLE" \
        '{outerUIForbidden:$outerUIForbidden,
          mutationGuardRequired:$mutationGuardRequired,
          mutationTargetVerified:$mutationTargetVerified,
          targetRole:$targetRole}'
}

input_click() {
    if (( $# < 2 || $# > 3 )); then
        printf 'Usage: linuxvm click X Y [left|right|middle]\n' >&2
        return 2
    fi
    local button="${3:-left}"
    if [[ "$button" != "left" && "$button" != "right" && "$button" != "middle" ]]; then
        printf 'Unknown mouse button: %s\n' "$button" >&2
        return 2
    fi
    /usr/bin/osascript - "$LINUXVM_UTM_NAME" "$1" "$2" "$button" <<'APPLESCRIPT'
on run argv
    set vmName to item 1 of argv
    set clickPosition to {(item 2 of argv) as integer, (item 3 of argv) as integer}
    set buttonName to item 4 of argv
    if buttonName is "right" then
        set buttonKind to «constant MsBtMsRt»
    else if buttonName is "middle" then
        set buttonKind to «constant MsBtMsMd»
    else
        set buttonKind to «constant MsBtMsLf»
    end if
    tell application "UTM"
        set targetVM to first virtual machine whose name is vmName
        input mouse click targetVM at clickPosition with mouse button buttonKind
    end tell
end run
APPLESCRIPT
}

require_utmctl
command="${1:-}"
if [[ -n "$command" ]]; then shift; fi

case "$command" in
    status) vm_status ;;
    target-id) target_id "$@" ;;
    factory-create) factory_create "$@" ;;
    factory-detach-media) factory_detach_media ;;
    guard-status) guard_status ;;
    up)
        ensure_running
        if guest_agent_ready; then guest_ipv4; else printf 'started (guest agent unavailable)\n'; fi
        ;;
    ip) guest_ipv4 ;;
    exec) guest_exec "$@" ;;
    shell) guest_shell ;;
    push) file_push "$@" ;;
    pull) file_pull "$@" ;;
    screenshot)
        linuxvm_assert_outer_ui_allowed
        exec "$PROVIDER_DIR/screenshot" "$@"
        ;;
    click)
        linuxvm_assert_outer_ui_allowed
        input_click "$@"
        ;;
    drag)
        linuxvm_assert_outer_ui_allowed
        host_control drag "$LINUXVM_UTM_NAME" "$LINUXVM_DISPLAY_WIDTH" \
            "$LINUXVM_DISPLAY_HEIGHT" "$@"
        ;;
    type)
        linuxvm_assert_outer_ui_allowed
        input_text "$@"
        ;;
    key)
        linuxvm_assert_outer_ui_allowed
        input_key "$@"
        ;;
    scan)
        linuxvm_assert_outer_ui_allowed
        input_scan_codes "$@"
        ;;
    permissions) host_control permissions ;;
    window-info)
        linuxvm_assert_outer_ui_allowed
        host_control window-info "$LINUXVM_UTM_NAME"
        ;;
    host-state) host_control host-state ;;
    suspend)
        linuxvm_assert_mutation_target
        "$LINUXVM_UTMCTL" suspend --save-state "$LINUXVM_UTM_NAME"
        ;;
    reboot) guest_reboot ;;
    shutdown) guest_shutdown ;;
    force-stop)
        linuxvm_assert_mutation_target
        "$LINUXVM_UTMCTL" stop --force "$LINUXVM_UTM_NAME"
        ;;
    disposable)
        linuxvm_assert_mutation_target
        [[ "$(vm_status)" == "stopped" ]] || {
            printf 'Disposable start requires a stopped VM\n' >&2; exit 1;
        }
        "$LINUXVM_UTMCTL" start "$LINUXVM_UTM_NAME" --disposable
        ;;
    clone)
        linuxvm_assert_mutation_target
        (( $# == 1 )) || { printf 'Usage: linuxvm clone NEW_NAME\n' >&2; exit 2; }
        "$LINUXVM_UTMCTL" clone "$LINUXVM_UTM_NAME" --name "$1"
        ;;
    *) usage >&2; exit 2 ;;
esac
