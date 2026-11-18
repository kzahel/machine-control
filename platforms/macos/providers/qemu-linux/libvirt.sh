# Libvirt workspace wiring for the Intel macOS adapter.

macvm_libvirt_shutdown() {
    if [[ "${MACVM_LIBVIRT_ALLOW_SSH_SHUTDOWN:-false}" != true ]]; then
        "$libvirt_core" shutdown
        return
    fi
    if MC_LIBVIRT_SHUTDOWN_TIMEOUT=12 "$libvirt_core" shutdown; then
        return 0
    fi
    local state command_line
    state="$(vm_status)" || return
    [[ "$state" == running ]] || { [[ "$state" == off ]]; return; }
    ssh_select || return
    remote /usr/bin/true </dev/null || return
    command_line="$(remote_command /usr/bin/sudo -S -p '' /sbin/shutdown -h now)" || return
    PYTHONPATH="$root/platforms/macos/providers/qemu-linux" python3 -c '
import os, sys
from vnc import stored_password
try:
    password = stored_password(os.environ["MACVM_QEMU_LOGIN_SECRET_FILE"])
except (KeyError, ValueError, OSError):
    raise SystemExit("The stored shutdown credential is unavailable")
sys.stdout.buffer.write(password + b"\n")
' | timeout 15 "${ssh_base[@]}" "$command_line" || true
    for _ in {1..40}; do
        state="$(vm_status)" || return
        if [[ "$state" == off ]]; then
            printf 'stopped\n'
            return 0
        fi
        sleep 1
    done
    printf 'The guest did not shut down after a single SSH request\n' >&2
    return 1
}

macvm_libvirt_workspaces() {
    source "$root/providers/workspaces/common.sh"
    workspace_require_tools || return
    if [[ -n "${MACHINE_CONTROL_WORKSPACE_HANDLE:-}" ]]; then
        workspace_refusal capabilities workspace_selection_conflict \
            'Workspace management cannot run through a selected workspace'
        return $?
    fi
    LIBVIRT_WORKSPACE_CORE="$libvirt_core"
    LIBVIRT_WORKSPACE_DOMAIN="$root/providers/libvirt-linux/workspace_domain.py"
    LIBVIRT_WORKSPACE_PLATFORM_BIN="$root/platforms/macos/bin/macvm-qemu"
    LIBVIRT_WORKSPACE_PROVIDER="$provider"
    LIBVIRT_WORKSPACE_STATE_DIR="$workspace_dir"
    LIBVIRT_WORKSPACE_CLAIM_STATE_DIR="$claim_dir"
    LIBVIRT_WORKSPACE_CURRENT_GUARDED=false
    LIBVIRT_WORKSPACE_DEVELOPMENT_NAME=
    LIBVIRT_WORKSPACE_DEVELOPMENT_ID=
    LIBVIRT_WORKSPACE_DEVELOPMENT_PROVEN=false
    LIBVIRT_WORKSPACE_READY_BASE_NAME="${MC_LIBVIRT_DOMAIN_NAME:-}"
    LIBVIRT_WORKSPACE_READY_BASE_ID="${MC_LIBVIRT_EXPECTED_UUID:-}"
    LIBVIRT_WORKSPACE_READY_BASE_PROVEN="${MACVM_LIBVIRT_READY_BASE_PROVEN:-false}"
    LIBVIRT_WORKSPACE_ALLOW_SHARED_BASE=false
    LIBVIRT_WORKSPACE_STORAGE_PATH="${MACVM_LIBVIRT_WORKSPACE_STORAGE_PATH:-}"
    LIBVIRT_WORKSPACE_MIN_FREE_BYTES="${MC_LIBVIRT_MIN_FREE_BYTES:-10737418240}"
    LIBVIRT_WORKSPACE_MAX_TEMPORARY="${MACVM_LIBVIRT_MAX_TEMPORARY:-1}"
    LIBVIRT_WORKSPACE_MAX_RETAINED="${MACVM_LIBVIRT_MAX_RETAINED:-1}"
    LIBVIRT_WORKSPACE_CANDIDATE_PREFIX=machine-control-macos
    LIBVIRT_WORKSPACE_NVRAM_DIRECTORY="${MACVM_LIBVIRT_NVRAM_DIRECTORY:-}"
    local layout
    layout="$("$libvirt_core" inspect)" || return
    LIBVIRT_WORKSPACE_NVRAM_TEMPLATE="$(jq -er .nvramPath <<<"$layout")" || return
    source "$root/providers/workspaces/libvirt-linux.sh"
    libvirt_workspace_main "$@"
}

macvm_libvirt_select_workspace() {
    local handle="${MACHINE_CONTROL_WORKSPACE_HANDLE:-}"
    [[ -n "$handle" ]] || return 0
    source "$root/providers/workspaces/common.sh"
    workspace_require_tools || return
    if [[ "$(workspace_receipt_field "$workspace_dir" "$handle" provider)" != "$provider" ]]; then
        printf 'Workspace receipt belongs to a different provider\n' >&2
        return 1
    fi
    local source_id
    source_id="$(workspace_receipt_field "$workspace_dir" "$handle" source.id)" || return
    if [[ "$source_id" != "${MC_LIBVIRT_EXPECTED_UUID:-}" ]]; then
        printf 'Workspace receipt belongs to a different source domain\n' >&2
        return 1
    fi
    MC_LIBVIRT_DOMAIN_NAME="$(workspace_receipt_field "$workspace_dir" "$handle" target.name)" || return
    MC_LIBVIRT_EXPECTED_UUID="$(workspace_receipt_field "$workspace_dir" "$handle" target.id)" || return
    export MC_LIBVIRT_DOMAIN_NAME MC_LIBVIRT_EXPECTED_UUID
}
